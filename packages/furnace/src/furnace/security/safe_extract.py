"""Safe extraction of untrusted ZIP / tar archives.

Rejects: absolute paths, ``..`` traversal, drive letters, NUL bytes, symlinks,
hardlinks, devices/FIFOs, too many entries, too many bytes (enforced while
streaming, not from declared sizes), and suspicious per-entry compression
ratios. Nested archives are stored as files, never expanded. Entries whose
names are invalid on the host OS are skipped and reported.
"""

from __future__ import annotations

import os
import stat
import tarfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

_WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
_CHUNK = 1 << 16


class ArchiveRejected(Exception):
    """The archive as a whole is unsafe or over limits; nothing should be used."""


@dataclass(frozen=True)
class ExtractLimits:
    max_entries: int = 20_000
    max_total_bytes: int = 500 * 2**20
    max_entry_bytes: int = 100 * 2**20
    max_ratio: float = 100.0  # uncompressed / compressed, per entry
    ratio_min_bytes: int = 2**20  # ratio check applies to entries larger than this


@dataclass
class ExtractStats:
    files: int = 0
    bytes: int = 0
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (name, reason)


def _safe_relpath(name: str, strip_components: int = 0) -> PurePosixPath | None:
    """Validate an archive member name; return a safe relative path or None to skip.
    Raises ArchiveRejected for names that indicate an attack."""
    if "\x00" in name:
        raise ArchiveRejected(f"NUL byte in member name {name!r}")
    norm = name.replace("\\", "/")
    if norm.startswith("/") or (len(norm) > 1 and norm[1] == ":"):
        raise ArchiveRejected(f"absolute path in archive: {name!r}")
    parts = [p for p in norm.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise ArchiveRejected(f"path traversal in archive: {name!r}")
    parts = parts[strip_components:]
    if not parts:
        return None
    return PurePosixPath(*parts)


def _host_invalid(rel: PurePosixPath) -> str | None:
    if os.name == "nt":
        for p in rel.parts:
            if p.split(".")[0].upper() in _WINDOWS_RESERVED or any(c in p for c in '<>:"|?*'):
                return "name invalid on this host"
            if p.endswith((" ", ".")):
                return "name invalid on this host"
    return None


def _target(dest: Path, rel: PurePosixPath) -> Path:
    target = (dest / Path(*rel.parts)).resolve()
    if not target.is_relative_to(dest):
        raise ArchiveRejected(f"member escapes destination: {rel}")
    return target


def _copy_limited(src, dst: Path, stats: ExtractStats, limits: ExtractLimits) -> int:
    written = 0
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("wb") as out:
        while True:
            block = src.read(_CHUNK)
            if not block:
                break
            written += len(block)
            if written > limits.max_entry_bytes:
                raise ArchiveRejected(
                    f"entry larger than {limits.max_entry_bytes} bytes: {dst.name}"
                )
            if stats.bytes + written > limits.max_total_bytes:
                raise ArchiveRejected(f"archive expands beyond {limits.max_total_bytes} bytes")
            out.write(block)
    return written


def safe_extract_zip(src: Path, dest: Path, limits: ExtractLimits | None = None) -> ExtractStats:
    limits = limits or ExtractLimits()
    dest = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    stats = ExtractStats()
    try:
        zf = zipfile.ZipFile(src)
    except zipfile.BadZipFile as exc:
        raise ArchiveRejected(f"not a valid zip: {exc}") from exc
    with zf:
        infos = zf.infolist()
        if len(infos) > limits.max_entries:
            raise ArchiveRejected(f"archive has {len(infos)} entries (limit {limits.max_entries})")
        for info in infos:
            rel = _safe_relpath(info.filename)
            if rel is None or info.is_dir():
                continue
            mode = (info.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode):
                raise ArchiveRejected(f"symlink in archive: {info.filename!r}")
            if mode and not stat.S_ISREG(mode) and stat.S_IFMT(mode) != 0:
                raise ArchiveRejected(f"special file in archive: {info.filename!r}")
            if (
                info.file_size > limits.ratio_min_bytes
                and info.compress_size > 0
                and info.file_size / info.compress_size > limits.max_ratio
            ):
                raise ArchiveRejected(f"compression ratio too high for {info.filename!r}")
            if reason := _host_invalid(rel):
                stats.skipped.append((info.filename, reason))
                continue
            target = _target(dest, rel)
            with zf.open(info) as fsrc:
                stats.bytes += _copy_limited(fsrc, target, stats, limits)
            stats.files += 1
    return stats


def safe_extract_tar(
    src: Path, dest: Path, limits: ExtractLimits | None = None, *, strip_components: int = 0
) -> ExtractStats:
    """Extract a (possibly gzip-compressed) tar. GitHub tarballs wrap everything in
    one top-level directory: pass strip_components=1."""
    limits = limits or ExtractLimits()
    dest = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    stats = ExtractStats()
    entries = 0
    try:
        tf = tarfile.open(src, mode="r:*")  # noqa: SIM115 - closed below
    except tarfile.TarError as exc:
        raise ArchiveRejected(f"not a valid tar: {exc}") from exc
    with tf:
        for member in tf:  # streaming: never call getmembers() on untrusted input
            entries += 1
            if entries > limits.max_entries:
                raise ArchiveRejected(f"archive has more than {limits.max_entries} entries")
            if member.type in (tarfile.XHDTYPE, tarfile.XGLTYPE):
                continue  # pax headers
            rel = _safe_relpath(member.name, strip_components)
            if rel is None or member.isdir():
                continue
            if member.issym() or member.islnk():
                raise ArchiveRejected(f"link in archive: {member.name!r}")
            if not member.isfile():
                raise ArchiveRejected(f"special file in archive: {member.name!r}")
            if reason := _host_invalid(rel):
                stats.skipped.append((member.name, reason))
                continue
            target = _target(dest, rel)
            fsrc = tf.extractfile(member)
            if fsrc is None:
                continue
            with fsrc:
                stats.bytes += _copy_limited(fsrc, target, stats, limits)
            stats.files += 1
    return stats
