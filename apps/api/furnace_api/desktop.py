"""Installed desktop entry point: private loopback Studio, no terminal or token file."""

from __future__ import annotations

import argparse
import secrets
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

from furnace_api.studio import create_app


class DesktopService:
    def __init__(self, workspace: Path, artifacts: Path | None = None):
        self.token = secrets.token_urlsafe(32)
        self.socket = socket.socket()
        self.socket.bind(("127.0.0.1", 0))
        self.url = f"http://127.0.0.1:{self.socket.getsockname()[1]}"
        self.server = uvicorn.Server(
            uvicorn.Config(
                create_app(workspace, self.token, artifacts),
                host="127.0.0.1",
                access_log=False,
                log_config=None,
                timeout_graceful_shutdown=5,
            )
        )
        self.error = False
        self.thread = threading.Thread(target=self._run, name="Furnace Studio")

    def _run(self) -> None:
        try:
            self.server.run(sockets=[self.socket])
        except (Exception, SystemExit):
            self.error = True
        finally:
            self.socket.close()

    def start(self, timeout: float = 30) -> None:
        self.thread.start()
        deadline = time.monotonic() + timeout
        while self.thread.is_alive() and not self.server.started:
            if time.monotonic() > deadline:
                self.server.should_exit = True
                raise RuntimeError(
                    "Studio startup is taking too long. Close Furnace and check Docker."
                )
            time.sleep(0.05)
        if not self.server.started:
            raise RuntimeError(
                "Studio could not open this workspace. It may already be open in another Furnace window."
            )

    def open_browser(self) -> None:
        webbrowser.open(self.url + "/#session=" + self.token)

    def stop(self, timeout: float = 30) -> bool:
        self.server.should_exit = True
        self.thread.join(timeout)
        return not self.thread.is_alive()


def main() -> None:
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.SetProcessDPIAware()
    import tkinter as tk
    from tkinter import messagebox, ttk

    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path.home() / ".furnace" / "studio")
    parser.add_argument("--artifacts", type=Path)
    args = parser.parse_args()
    window = tk.Tk()
    window.title("Furnace")
    icon = Path(sys.executable).resolve().parents[1] / "furnace.ico"
    if sys.platform == "win32" and icon.is_file():
        window.iconbitmap(default=str(icon))
    window.geometry("440x245")
    window.resizable(False, False)
    frame = ttk.Frame(window, padding=28)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Furnace Studio", font=("Segoe UI", 20, "bold")).pack(anchor="w")
    status = ttk.Label(frame, text="Opening your local workspace…", wraplength=380)
    status.pack(anchor="w", pady=16)
    service = DesktopService(args.workspace, args.artifacts)
    closing = False

    def finish_quit() -> None:
        service.server.should_exit = True
        if service.thread.is_alive():
            window.after(100, finish_quit)
        else:
            window.destroy()

    def quit_app() -> None:
        nonlocal closing
        closing = True
        status.configure(text="Stopping Studio and releasing its workspace…")
        open_button.configure(state="disabled")
        quit_button.configure(state="disabled")
        finish_quit()

    open_button = ttk.Button(
        frame, text="Open Studio", command=service.open_browser, state="disabled"
    )
    open_button.pack(side="left", pady=12)
    quit_button = ttk.Button(frame, text="Quit Furnace", command=quit_app)
    quit_button.pack(side="right", pady=12)
    window.protocol("WM_DELETE_WINDOW", quit_app)

    def started() -> None:
        if closing:
            return
        if service.server.started:
            status.configure(
                text="Studio is running privately on this machine.\nClosing this window stops Studio and its owned workers."
            )
            open_button.configure(state="normal")
            service.open_browser()
        elif not service.thread.is_alive():
            messagebox.showerror(
                "Furnace could not start",
                "This workspace may already be open. Close its other Furnace window and try again.",
            )
            quit_app()
        else:
            window.after(100, started)

    service.thread.start()
    window.after(100, started)
    window.mainloop()


if __name__ == "__main__":
    main()
