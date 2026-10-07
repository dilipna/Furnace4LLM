"""`furnace` command line for the laptop runner.

  furnace gh-check                                   # verify the GitHub App id, key and installations
  furnace gh-forge OWNER/REPO [--open-pr]            # Forge: plan + sandbox-validate, then a draft PR
  furnace gh-guard OWNER/REPO PR --suite FILE.py     # Guard: targeted checks -> GitHub check run
  furnace gh-repair OWNER/REPO PR --suite FILE.py [--open-pr]   # verified repair -> draft PR

Configuration (environment or .env): FURNACE_GITHUB_APP_ID, FURNACE_GITHUB_PRIVATE_KEY_PATH,
FURNACE_LAB_BASE_URL (default http://localhost:8100/v1), FURNACE_LAB_MODEL (default lab).
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import yaml
from furnace_bench.schema import AdapterName, BenchTarget

from furnace.github.client import GitHubApp, GitHubError
from furnace.settings import get_settings

DEFAULT_QUESTIONS = [
    "What can you help me with?",
    "How do I get started?",
    "What does this product cost?",
    "How do I contact support?",
]


def _app() -> GitHubApp:
    s = get_settings()
    if not s.github_app_id or not s.github_private_key_path:
        raise SystemExit(
            "set FURNACE_GITHUB_APP_ID and FURNACE_GITHUB_PRIVATE_KEY_PATH (see docs/github-app.md)"
        )
    key = Path(s.github_private_key_path).read_text(encoding="utf-8")
    return GitHubApp(app_id=s.github_app_id, private_key_pem=key)


def _questions(path: str | None) -> list[str]:
    """JSON list of strings, or of objects with a "question" field (e.g. docs/facts.json)."""
    if not path:
        return DEFAULT_QUESTIONS
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    qs = [q if isinstance(q, str) else q["question"] for q in data]
    if not qs:
        raise SystemExit(f"{path} has no questions")
    return qs


def _suite(path: str) -> list[Any]:
    """Load the suite list (SUITE, or the first *_SUITE) from a Python file."""
    spec = importlib.util.spec_from_file_location("furnace_user_suite", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load suite from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for name in ["SUITE", *sorted(n for n in vars(mod) if n.endswith("_SUITE"))]:
        if isinstance(getattr(mod, name, None), list):
            return getattr(mod, name)
    raise SystemExit(f"{path} defines no SUITE list")


def _target(no_endpoint: bool) -> BenchTarget | None:
    if no_endpoint:
        return None
    s = get_settings()
    return BenchTarget(
        adapter=AdapterName.vllm, base_url=s.lab_base_url, model=s.lab_model, label="lab"
    )


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2, default=str))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="furnace")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("gh-check", help="verify the GitHub App configuration")
    f = sub.add_parser("gh-forge", help="Forge a repository's default branch")
    f.add_argument("repo")
    f.add_argument("--questions")
    f.add_argument("--workload", help="workload fingerprint YAML to install as a benchmark config")
    f.add_argument("--open-pr", action="store_true", help="explicit write consent: open a draft PR")
    for name in ("gh-guard", "gh-repair"):
        g = sub.add_parser(name)
        g.add_argument("repo")
        g.add_argument("pr", type=int)
        g.add_argument("--suite", required=True, help="Python file defining the suite list")
        g.add_argument("--questions")
        g.add_argument(
            "--no-endpoint", action="store_true", help="skip checks that need an inference endpoint"
        )
        if name == "gh-guard":
            g.add_argument("--max-prompt-tokens", type=int)
        else:
            g.add_argument(
                "--open-pr", action="store_true", help="explicit write consent: open a draft PR"
            )
    a = p.parse_args(argv)
    say = lambda m: print(f"  {m}", file=sys.stderr, flush=True)  # noqa: E731

    from furnace.github import flows

    try:
        if a.cmd == "gh-check":
            _print(asyncio.run(_app().app_info()))
        elif a.cmd == "gh-forge":
            wl = (
                yaml.safe_load(Path(a.workload).read_text(encoding="utf-8")) if a.workload else None
            )
            _print(
                asyncio.run(
                    flows.forge_pr(
                        _app(),
                        a.repo,
                        questions=_questions(a.questions),
                        workload=wl,
                        open_pr=a.open_pr,
                        progress=say,
                    )
                )
            )
        elif a.cmd == "gh-guard":
            _print(
                asyncio.run(
                    flows.guard_pr(
                        _app(),
                        a.repo,
                        a.pr,
                        suite=_suite(a.suite),
                        target=_target(a.no_endpoint),
                        questions=_questions(a.questions),
                        max_prompt_tokens=a.max_prompt_tokens,
                        progress=say,
                    )
                )
            )
        elif a.cmd == "gh-repair":
            _print(
                asyncio.run(
                    flows.repair_pr(
                        _app(),
                        a.repo,
                        a.pr,
                        suite=_suite(a.suite),
                        target=_target(a.no_endpoint),
                        questions=_questions(a.questions),
                        open_pr=a.open_pr,
                        progress=say,
                    )
                )
            )
    except GitHubError as exc:
        print(f"GitHub: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
