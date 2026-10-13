"""Held-out set 6, selection step (protocol: docs/scanner-eval-set6.md section 2).

  uv run python bench/set6_select.py tree <owner/repo>...   # rule 3 facts from the git tree

Prints, per repository, the default branch head commit and the count of non-test Python
files (paths under tests/ or test/, or named test_*.py / *_test.py / conftest.py, are
tests). Reads only the GitHub API; no Furnace code runs on the repository here.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request

API = "https://api.github.com"
TEST = re.compile(r"(^|/)(tests?/|test_[^/]*\.py$|[^/]*_test\.py$|conftest\.py$)")


def get(url: str) -> dict:
    if not url.startswith(API):
        raise ValueError(f"not a GitHub API URL: {url}")
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})  # noqa: S310
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 - fixed https host
        return json.load(r)


def tree(full: str) -> dict:
    repo = get(f"{API}/repos/{full}")
    branch = repo["default_branch"]
    head = get(f"{API}/repos/{full}/commits/{branch}")["sha"]
    t = get(f"{API}/repos/{full}/git/trees/{head}?recursive=1")
    py = [x["path"] for x in t["tree"] if x["type"] == "blob" and x["path"].endswith(".py")]
    app_py = [p for p in py if not TEST.search(p)]
    langs = get(f"{API}/repos/{full}/languages")
    total = sum(langs.values()) or 1
    return {
        "repo": full,
        "branch": branch,
        "commit": head,
        "python_files_non_test": len(app_py),
        "truncated": t.get("truncated", False),
        "python_share_bytes": round(langs.get("Python", 0) / total, 2),
        "top_dirs": sorted({p.split("/")[0] for p in app_py})[:12],
    }


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] != "tree":
        raise SystemExit(__doc__)
    for full in sys.argv[2:]:
        try:
            print(json.dumps(tree(full)))
        except Exception as exc:  # report and continue: a failure is recorded, not hidden
            print(json.dumps({"repo": full, "error": f"{type(exc).__name__}: {exc}"}))
