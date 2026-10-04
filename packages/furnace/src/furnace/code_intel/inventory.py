"""Repository inventory: which files exist, what language, which are parseable."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".next",
    "out",
    "target",
    ".tox",
    "site-packages",
    "vendor",
    ".idea",
    ".vscode",
}

LANG_BY_EXT = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".md": "markdown",
    ".mdx": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".json": "json",
    ".jsonl": "jsonl",
    ".txt": "text",
    ".jinja": "template",
    ".j2": "template",
    ".prompt": "template",
    ".sql": "sql",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".gif": "image",
}

MAX_PARSE_BYTES = 2 * 2**20


@dataclass
class RepoFile:
    path: str  # posix, relative to repo root
    lang: str
    bytes: int
    sha256: str
    binary: bool
    parseable: bool


@dataclass
class Inventory:
    root: Path
    files: list[RepoFile] = field(default_factory=list)

    @property
    def languages(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for f in self.files:
            if f.lang not in ("other", "image", "json", "jsonl", "text"):
                out[f.lang] = out.get(f.lang, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: -kv[1]))

    def by_lang(self, lang: str) -> list[RepoFile]:
        return [f for f in self.files if f.lang == lang and f.parseable]

    def find(self, *names: str) -> list[RepoFile]:
        lowered = {n.lower() for n in names}
        return [f for f in self.files if Path(f.path).name.lower() in lowered]

    def read(self, f: RepoFile) -> str:
        return (self.root / f.path).read_text(encoding="utf-8", errors="replace")


def _lang(path: Path) -> str:
    name = path.name.lower()
    if name.startswith("dockerfile"):
        return "dockerfile"
    if name.startswith(".env"):
        return "dotenv"
    return LANG_BY_EXT.get(path.suffix.lower(), "other")


def build_inventory(root: Path) -> Inventory:
    root = root.resolve()
    inv = Inventory(root=root)
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if (
            any(part in SKIP_DIRS for part in rel.parts[:-1])
            or not path.is_file()
            or path.is_symlink()
        ):
            continue
        data = path.read_bytes()
        binary = b"\x00" in data[:8192]
        lang = _lang(path)
        inv.files.append(
            RepoFile(
                path=rel.as_posix(),
                lang=lang,
                bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
                binary=binary,
                parseable=not binary and len(data) <= MAX_PARSE_BYTES and lang != "image",
            )
        )
    return inv
