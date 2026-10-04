"""Source templates for Forge artifacts.

Generated files are self-contained: they depend only on pytest and the
application's own code, never on Furnace, so a customer can keep them forever.
Placeholders are `__NAME__` tokens (no str.format, so code braces need no escaping).
"""

from __future__ import annotations

import re

_PLACEHOLDER = re.compile(r"__[A-Z][A-Z_]*__")


def fill(template: str, **values: object) -> str:
    out = template
    for k, v in values.items():
        out = out.replace(f"__{k}__", str(v))
    left = _PLACEHOLDER.findall(out)
    if left:
        raise ValueError(f"unfilled placeholders: {sorted(set(left))}")
    return out


PREFIX_TEST = '''"""Installed by Furnace Forge.

Guards the shared prompt prefix: every request must start with the same text, so the
serving engine can reuse the cached prefill of that prefix (prefix/KV caching).
A per-request value (id, timestamp, user name) placed before the static text would
silently disable that reuse and raise time-to-first-token.
Measured when installed: two different requests shared __SHARED__ leading characters.
"""

from furnace_harness import render

MIN_SHARED_CHARS = __THRESHOLD__
QUESTIONS = __QUESTIONS__


def _text(question):
    return "".join(f"{m['role']}\\n{m['content']}\\n" for m in render(question))


def _shared(a, b):
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def test_prompt_prefix_is_shared_across_requests():
    first = _text(QUESTIONS[0])
    for q in QUESTIONS[1:]:
        shared = _shared(first, _text(q))
        assert shared >= MIN_SHARED_CHARS, (
            f"requests diverge after {shared} characters (need {MIN_SHARED_CHARS}); "
            f"first difference: {first[shared:shared + 60]!r}"
        )
'''

APPROVAL_TEST = '''"""Installed by Furnace Forge.

`__FUNC__` (__LOCATION__) performs __EFFECT__ side effect and is guarded by
`if not __PARAM__`. This test fails if that guard is removed: calling it with
__PARAM__=False must not perform any outbound write.
"""

import pytest

import __MODULE__ as target


class _NoOutbound(Exception):
    pass


def _forbid(*args, **kwargs):
    raise _NoOutbound("outbound call attempted without approval")


def test___FUNC___requires_approval(monkeypatch):
__PATCHES__
    with pytest.raises(Exception) as exc:
        target.__FUNC__(__ARGS__)
    assert not isinstance(exc.value, _NoOutbound), "side effect executed without approval"
'''

TIMEOUT_TEST = '''"""Installed by Furnace Forge.

The LLM client must carry an explicit timeout, so a stalled model server cannot
hold a user request open for the SDK default (10 minutes for the OpenAI SDK).
"""

import __MODULE__ as target


def test_llm_client_has_explicit_timeout():
    timeout = target.__VAR__.timeout
    seconds = getattr(timeout, "read", timeout)
    assert seconds is not None and float(seconds) <= __MAX_SECONDS__
'''

EVAL_RUNNER = '''"""Installed by Furnace Forge: run the app's answer path on an eval dataset and
apply deterministic checks. Needs a reachable model endpoint (the app's own
LLM_BASE_URL); it is run by Furnace Guard on PRs, not by plain `pytest`.

    python evals/run_evals.py evals/datasets/questions.jsonl --out evals/results.json
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from furnace_harness import render  # noqa: E402
from __LLM_MODULE__ import __CLIENT__ as client  # noqa: E402

CITATION = re.compile(r"__CITATION_RE__")
NOT_FOUND = re.compile(r"__NOT_FOUND_RE__")


def check_citations(answer, retrieved):
    cited = set(CITATION.findall(answer))
    if not cited:
        if NOT_FOUND.search(answer):
            return "PASS", "documented not-found answer"
        return "FAIL", "answer has no citation"
    unknown = sorted(cited - set(retrieved))
    if unknown:
        return "FAIL", "cites ids that were not retrieved: " + ", ".join(unknown)
    return "PASS", f"{len(cited)} cited id(s), all retrieved"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--model", default="__MODEL__")
    ap.add_argument("--max-tokens", type=int, default=__MAX_TOKENS__)
    ap.add_argument("--out", default="evals/results.json")
    a = ap.parse_args()
    rows = [json.loads(line) for line in Path(a.dataset).read_text(encoding="utf-8").splitlines() if line.strip()]
    results = []
    for row in rows:
        messages = render(row["question"])
        context = messages[-1]["content"]
        retrieved = CITATION.findall(context)
        resp = client.chat.completions.create(model=a.model, messages=messages, max_tokens=a.max_tokens, temperature=0)
        answer = resp.choices[0].message.content or ""
        verdict, reason = check_citations(answer, retrieved)
        results.append({"id": row["id"], "question": row["question"], "answer": answer, "retrieved": retrieved,
                        "expected_doc": row.get("expected_doc"), "citation_required": verdict, "reason": reason})
    passed = sum(r["citation_required"] == "PASS" for r in results)
    Path(a.out).write_text(json.dumps({"n": len(results), "citation_required_pass": passed, "results": results}, indent=2), encoding="utf-8")
    print(f"citation_required: {passed}/{len(results)} PASS")


if __name__ == "__main__":
    main()
'''

JUDGE_SPEC = """# Installed by Furnace Forge. Single-failure-mode LLM judge, run by Furnace Guard with
# your own model key (BYOK). Results are advisory until calibrated against human labels
# (TPR and TNR >= 0.8 on held-out labels).
key: judge:ungrounded_answer
failure_mode: ungrounded answer
fail_when: >-
  the answer states a factual claim about the product (a number, limit, price, procedure,
  policy or capability) that is not supported by the retrieved context, or contradicts it.
pass_when: >-
  every factual claim is supported by the context, or the answer says the information is
  not in the documentation.
model:
  provider: groq          # groq | openrouter | openai | ollama
  name: llama-3.3-70b-versatile
  api_key_env: GROQ_API_KEY
calibration:
  status: uncalibrated
  min_tpr: 0.8
  min_tnr: 0.8
"""

CI_WORKFLOW = """# Installed by Furnace Forge: deterministic reliability tests, no model or secrets needed.
name: furnace

on:
  pull_request:
  push:
    branches: [__BRANCH__]

jobs:
  reliability:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt pytest
      - run: python -m pytest -q tests/furnace
"""

FURNACE_YAML = """# Installed by Furnace Forge. Read by Furnace Guard on every pull request.
version: 1
harness: furnace_harness.py::render
slo:
  ttft_p95_ms: __SLO_TTFT__
  max_failure_rate: 0.01
policy:
  perf_regression:
    metric: ttft_p95_ms
    warn_pct: 10
    block_pct: 25
  quality:
    citation_required: {min_pass_rate_delta: -0.05}
evals:
  dataset: evals/datasets/questions.jsonl
  runner: evals/run_evals.py
  judges: [evals/judges/ungrounded_answer.yaml]
benchmarks:
  workloads: benchmarks/workloads.yaml
  endpoint_env: LLM_BASE_URL
"""

PROMPT_FILE = """---
id: __ID__
version: 1
extracted_from: __SOURCE__
---
"""
