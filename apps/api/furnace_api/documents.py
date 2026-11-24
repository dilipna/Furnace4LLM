"""Bounded local extraction; document content travels through pipes, never temp files."""

from __future__ import annotations

import ctypes
import json
import subprocess
import sys
import threading
from ctypes import wintypes

from fastapi import HTTPException


class WindowsJob:
    """Bound the parser's memory/CPU and kill it when its owning handle closes."""

    def __init__(self, pid: int):
        if sys.platform != "win32":
            raise OSError("Windows Job Objects are only available on Windows")

        class Basic(ctypes.Structure):
            _fields_ = [
                ("process_time", ctypes.c_longlong),
                ("job_time", ctypes.c_longlong),
                ("flags", wintypes.DWORD),
                ("min_working", ctypes.c_size_t),
                ("max_working", ctypes.c_size_t),
                ("active", wintypes.DWORD),
                ("affinity", ctypes.c_size_t),
                ("priority", wintypes.DWORD),
                ("scheduling", wintypes.DWORD),
            ]

        class Counters(ctypes.Structure):
            _fields_ = [
                (name, ctypes.c_ulonglong)
                for name in (
                    "read_ops",
                    "write_ops",
                    "other_ops",
                    "read_bytes",
                    "write_bytes",
                    "other_bytes",
                )
            ]

        class Limits(ctypes.Structure):
            _fields_ = [
                ("basic", Basic),
                ("io", Counters),
                ("process_memory", ctypes.c_size_t),
                ("job_memory", ctypes.c_size_t),
                ("peak_process", ctypes.c_size_t),
                ("peak_job", ctypes.c_size_t),
            ]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel = kernel
        self.handle = kernel.CreateJobObjectW(None, None)
        limits = Limits()
        limits.basic.flags = 0x2000 | 0x100 | 0x2  # kill on close, process memory, CPU time
        limits.basic.process_time = 8 * 10_000_000
        limits.process_memory = 384 * 1024**2
        process = kernel.OpenProcess(0x100 | 0x1, False, pid)
        try:
            if (
                not self.handle
                or not process
                or not kernel.SetInformationJobObject(
                    self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
                )
                or not kernel.AssignProcessToJobObject(self.handle, process)
            ):
                raise OSError("Cannot establish parser resource limits")
        except Exception:
            self.close()
            raise
        finally:
            if process:
                kernel.CloseHandle(process)

    def close(self) -> None:
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


PARSERS = threading.BoundedSemaphore(2)


def extract_document(kind: str, data: str) -> dict:
    if not PARSERS.acquire(blocking=False):
        raise HTTPException(429, "Two local documents are already being read; try again shortly")
    try:
        return _extract_document(kind, data)
    finally:
        PARSERS.release()


def _extract_document(kind: str, data: str) -> dict:
    job = None
    process = subprocess.Popen(
        [sys.executable, "-I", "-m", "furnace_api.document_worker"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        if sys.platform == "win32":
            job = WindowsJob(process.pid)
        stdout, _ = process.communicate(
            json.dumps({"kind": kind, "data": data}).encode(), timeout=12
        )
        if process.returncode:
            raise ValueError("Parser resource limit or failure")
        result = json.loads(stdout)
        if result.get("error"):
            raise HTTPException(422, result["error"])
        return {
            "text": result["text"],
            "processing": "local; memory only",
            "ocr": False,
            "warning": "PDF reading order can differ from the page. Images and scanned sections are not read."
            if kind == "pdf"
            else "DOCX main-body text only. Headers, footnotes, comments and embedded objects are not read."
            if kind == "docx"
            else "",
        }
    except (ValueError, OSError, subprocess.TimeoutExpired):
        raise HTTPException(
            422,
            "Document parsing failed or exceeded its local resource limit. Try a smaller UTF-8 text file.",
        ) from None
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        if job:
            job.close()
