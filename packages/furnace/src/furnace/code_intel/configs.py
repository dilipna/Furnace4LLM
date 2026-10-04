"""Manifests, compose files, YAML/TOML configs, dotenv examples."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import PurePosixPath
from typing import Any

import yaml

from furnace.code_intel.facts import Fact
from furnace.code_intel.inventory import Inventory, RepoFile
from furnace.code_intel.signatures import SERVING_IMAGES, lookup, normalize_dist_name
from furnace.contracts.common import Locator
from furnace.contracts.graph import NodeKind, node_key
from furnace.security.redact import redact

EXTRACTOR = "config@1"
_REQ_LINE = re.compile(r"^\s*([A-Za-z0-9_.\-\[\]]+)")
SERVING_FLAG = re.compile(r"^--([a-z0-9\-]+)(?:=(.*))?$")
CONFIG_SKIP = re.compile(
    r"(^|/)(\.github|node_modules|docker-compose|compose)[^/]*|pnpm-lock|package-lock|yarn\.lock"
)


def _line_of(text: str, needle: str) -> int | None:
    idx = text.find(needle)
    return text.count("\n", 0, idx) + 1 if idx >= 0 else None


def _fact(
    kind: str, key: str, data: dict[str, Any], f: RepoFile, line: int | None, excerpt: str
) -> Fact:
    return Fact(
        kind=kind,
        key=key,
        data=data,
        locator=Locator(path=f.path, line_start=line, line_end=line),
        excerpt=redact(excerpt)[:480],
        extractor=f"{EXTRACTOR}.{kind}",
    )


# ---------------------------------------------------------------------------- dependencies


def _dep_fact(name: str, f: RepoFile, text: str, ecosystem: str) -> Fact:
    sig = lookup(name)
    return _fact(
        "dependency",
        f"dependency:{ecosystem}:{normalize_dist_name(name)}",
        {
            "name": normalize_dist_name(name),
            "ecosystem": ecosystem,
            "category": sig.category if sig else None,
            "provider": sig.provider if sig else None,
            "note": sig.note if sig else "",
        },
        f,
        _line_of(text, name),
        name,
    )


def extract_dependencies(inv: Inventory) -> list[Fact]:
    facts: list[Fact] = []
    for f in inv.files:
        name = PurePosixPath(f.path).name.lower()
        if not f.parseable or "node_modules" in f.path:
            continue
        text = (
            inv.read(f)
            if name in ("pyproject.toml", "package.json") or name.startswith("requirements")
            else ""
        )
        if name.startswith("requirements") and name.endswith(".txt"):
            for line in text.splitlines():
                if line.strip().startswith(("#", "-")):
                    continue
                m = _REQ_LINE.match(line)
                if m:
                    facts.append(_dep_fact(m.group(1).split("[")[0], f, text, "pypi"))
        elif name == "pyproject.toml":
            try:
                data = tomllib.loads(text)
            except tomllib.TOMLDecodeError:
                continue
            deps = list((data.get("project") or {}).get("dependencies") or [])
            for group in ((data.get("project") or {}).get("optional-dependencies") or {}).values():
                deps.extend(group)
            poetry = ((data.get("tool") or {}).get("poetry") or {}).get("dependencies") or {}
            deps.extend(k for k in poetry if k != "python")
            for d in deps:
                m = _REQ_LINE.match(d)
                if m:
                    facts.append(_dep_fact(m.group(1).split("[")[0], f, text, "pypi"))
        elif name == "package.json":
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue
            for section in ("dependencies", "devDependencies", "peerDependencies"):
                for dep in data.get(section) or {}:
                    facts.append(_dep_fact(dep, f, text, "npm"))
    return facts


# ---------------------------------------------------------------------------- compose


def _parse_command(cmd: Any) -> list[str]:
    if isinstance(cmd, list):
        return [str(c) for c in cmd]
    if isinstance(cmd, str):
        return cmd.split()
    return []


def extract_compose(inv: Inventory) -> list[Fact]:
    facts: list[Fact] = []
    for f in inv.files:
        name = PurePosixPath(f.path).name.lower()
        if not (
            name.startswith(("docker-compose", "compose")) and name.endswith((".yml", ".yaml"))
        ):
            continue
        text = inv.read(f)
        try:
            data = yaml.safe_load(text) or {}
        except yaml.YAMLError:
            continue
        for svc, spec in (data.get("services") or {}).items():
            if not isinstance(spec, dict):
                continue
            image = str(spec.get("image") or "")
            engine = next(
                (e for prefix, e in SERVING_IMAGES.items() if image.startswith(prefix)), None
            )
            ports: list[dict[str, int]] = []
            for p in spec.get("ports") or []:
                m = re.match(r"^(?:[\d.]+:)?(\d+):(\d+)", str(p))
                if m:
                    ports.append({"host": int(m.group(1)), "container": int(m.group(2))})
            env = spec.get("environment") or {}
            if isinstance(env, list):
                env = dict(e.split("=", 1) for e in env if "=" in e)
            argv = _parse_command(spec.get("command"))
            flags: dict[str, Any] = {}
            positional: list[str] = []
            for i, arg in enumerate(argv):
                m = SERVING_FLAG.match(arg)
                if m:
                    value: Any = m.group(2)
                    if value is None and i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                        value = argv[i + 1]
                    flags[m.group(1)] = True if value is None else value
                elif not (i > 0 and SERVING_FLAG.match(argv[i - 1]) and "=" not in argv[i - 1]):
                    positional.append(arg)
            model = flags.get("model") or (
                positional[0] if engine in ("vllm", "sglang") and positional else None
            )
            line = _line_of(text, f"{svc}:")
            facts.append(
                _fact(
                    "compose_service",
                    f"service:{svc}",
                    {
                        "service": svc,
                        "image": image or None,
                        "build": spec.get("build") is not None,
                        "engine": engine,
                        "ports": ports,
                        "environment": {k: redact(str(v)) for k, v in env.items()},
                        "depends_on": list(spec.get("depends_on") or []),
                        "gpu": "nvidia" in json.dumps(spec.get("deploy") or {}),
                    },
                    f,
                    line,
                    f"{svc}: image={image}",
                )
            )
            if engine:
                facts.append(
                    _fact(
                        "serving_config",
                        node_key(NodeKind.serving_config, f.path, svc),
                        {
                            "service": svc,
                            "engine": engine,
                            "image": image,
                            "model": model,
                            "flags": flags,
                            "ports": ports,
                        },
                        f,
                        line,
                        " ".join(argv)[:400],
                    )
                )
    return facts


# ---------------------------------------------------------------------------- configs


def _flatten(prefix: str, obj: Any, out: dict[str, Any]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            _flatten(f"{prefix}.{k}" if prefix else str(k), v, out)
    elif isinstance(obj, (str, int, float, bool)) or obj is None:
        out[prefix] = obj


def extract_configs(inv: Inventory) -> list[Fact]:
    facts: list[Fact] = []
    for f in inv.files:
        if f.lang not in ("yaml", "toml") or not f.parseable or CONFIG_SKIP.search(f.path):
            continue
        name = PurePosixPath(f.path).name.lower()
        if name in (
            "pyproject.toml",
            "poetry.lock",
            "uv.lock",
            "pnpm-workspace.yaml",
        ) or f.path.startswith(".github/"):
            continue
        text = inv.read(f)
        try:
            data = tomllib.loads(text) if f.lang == "toml" else yaml.safe_load(text)
        except (yaml.YAMLError, tomllib.TOMLDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        flat: dict[str, Any] = {}
        _flatten("", data, flat)
        for keypath, value in list(flat.items())[:500]:
            leaf = keypath.split(".")[-1]
            facts.append(
                _fact(
                    "config_key",
                    node_key(NodeKind.config_key, f"{f.path}#{keypath}"),
                    {
                        "file": f.path,
                        "keypath": keypath,
                        "value": redact(str(value)) if isinstance(value, str) else value,
                    },
                    f,
                    _line_of(text, f"{leaf}:") or _line_of(text, f"{leaf} ="),
                    f"{keypath}: {value}",
                )
            )
    return facts


def extract_dotenv(inv: Inventory) -> list[Fact]:
    facts: list[Fact] = []
    for f in inv.files:
        if f.lang != "dotenv" or not f.parseable:
            continue
        text = inv.read(f)
        for i, line in enumerate(text.splitlines(), 1):
            m = re.match(r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*(.*)$", line)
            if m:
                facts.append(
                    _fact(
                        "env_var",
                        f"env:{m.group(1)}",
                        {"name": m.group(1), "example_value": redact(m.group(2).strip())[:200]},
                        f,
                        i,
                        redact(line)[:200],
                    )
                )
    return facts


def extract_tests(inv: Inventory) -> list[Fact]:
    facts: list[Fact] = []
    for f in inv.files:
        name = PurePosixPath(f.path).name
        if f.lang == "python" and (name.startswith("test_") or name.endswith("_test.py")):
            facts.append(
                _fact(
                    "test_file",
                    f"test:{f.path}",
                    {"framework": "pytest", "path": f.path},
                    f,
                    1,
                    f.path,
                )
            )
        elif f.lang in ("typescript", "javascript") and re.search(
            r"\.(test|spec)\.[cm]?[jt]sx?$", name
        ):
            facts.append(
                _fact(
                    "test_file", f"test:{f.path}", {"framework": "js", "path": f.path}, f, 1, f.path
                )
            )
    return facts


def extract_all(inv: Inventory) -> list[Fact]:
    return [
        *extract_dependencies(inv),
        *extract_compose(inv),
        *extract_configs(inv),
        *extract_dotenv(inv),
        *extract_tests(inv),
    ]
