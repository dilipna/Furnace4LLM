# Held-out set 6: results and review (protocol `docs/scanner-eval-set6.md`)

Scanner frozen at 41ca529; five apps chosen by one pre-declared GitHub search
(`selection.md`); labels and expected findings committed in ebd5824 before any scan. Labels
by the developer agent, not independent. Three quantities, never combined:

| quantity | result | file |
|---|---|---|
| LLM call sites (first scan) | found **32/48** (67%, exact 95% CI 52-80%), precision **32/32** (CI 89-100%) | `rq1.md` (column "held-out set 6") |
| Blueprint findings | precision **39/77** (51%, CI 39-62%), recall **39/64** (61%, CI 48-73%) | `set6/findings.md` |
| Evidence links | **148/148** resolve (6 file-level) | `set6/citations.md` |

Per app, call sites: Soul-of-Waifu 24/27, BYO-LLM-WIKI 5/12, audiobook-creator 3/5,
mdflux 0/3, ps-fuzz 0/1. The pooled 32/48 is dominated by Soul-of-Waifu's 27 sites, which
are one pattern repeated (nine provider classes x three methods); the mean of per-app recall
is 0.38. Compared with sets 1-5 (first scans pooled 4/34), set 6 is higher; the sets are
different apps and are reported side by side, not pooled.

The headline point: every evidence link resolved while half of the emitted findings were
wrong. Link validity says nothing about finding correctness.

## Review of every disagreement (after the result; the numbers above are not changed)

Judged by the developer agent after seeing the output. "Label" = the pre-registered label or
its definition was wrong or too narrow; "scanner" = the scanner was wrong; "open" = defensible
either way.

**Missed call sites (16), all scanner:** raw HTTP chat requests (mdflux 3, Soul-of-Waifu's
Anthropic provider 3); LangChain chat models received as a function parameter or held in
`self.client` (BYO 7, ps-fuzz 1); Pydantic AI `Agent(...).run` (audiobook 2).

**Emitted, not expected (38):**
- Scanner, 32: `sec.tool_approval_boundary` on 28 functions that no model can call (ffmpeg,
  file saves, config writes, release scripts: audiobook 23, mdflux 4, ps-fuzz 1). The rule
  treats any side-effecting function as a tool. `eval.grounding_judge` on mdflux (no
  retrieval). BYO: `rel.fallback_gateway` and `eval.regression_suite` (it has explicit
  `max_retries=2` and Ragas evals, neither recognized). audiobook: `inf.prefix_instability`
  on a system message whose leading value is fixed per deployment (static analysis cannot
  tell; under the pre-declared definition the label stands).
- Label, 4: prompt constants whose names lack "prompt"/"instruction"/"system"
  (`_CROSSDOC_JUDGE`, `_REQUIREMENTS`, `_SKILL_JSON_SHAPE` in BYO; `ethical_compliance_template`
  in ps-fuzz). The naming rule in the labels was too narrow; the scanner was right.
- Open, 2: audiobook `inf.serving_baseline` (its default endpoint is a local LM Studio
  server: self-hosted, but not in the rule's engine list the labels mirrored); ps-fuzz
  `eval.grounding_judge` (its RAG-poisoning attack does retrieve; labeled as not RAG because
  it does not ground answers).

**Expected, not emitted (25):**
- Cascade from missed call sites, 8: every app-level rule needs an LLM call, so mdflux (0/3
  call sites) and ps-fuzz (0/1) lost timeout, fallback, eval, tracing and serving findings.
- Tools not recognized, 8 (BYO): LangChain `@tool` functions, and the MCP write path's
  approval gate.
- Prompts built inside functions, 8 (audiobook 7: f-string system prompts inside functions
  and Pydantic AI `system_prompt=`, and the prefix rules that depend on them) and 1 (BYO:
  the deep agent's `system_prompt=` constant).
- audiobook `obs.genai_tracing`, 1: scanner.

Re-scored with the four label corrections only (for orientation, not a result): precision
43/77, recall 43/68. The pre-registered numbers stand.

## What this says about the scanner

It is accurate where it fires on call sites (no false positive in 48 labeled sites) but
misses common constructs (raw HTTP, injected LangChain models, Pydantic AI, LangChain
tools), and each missed call site silently removes the app-level findings that depend on it.
Its tool rule is wrong in kind: it flags side-effecting functions that no model can invoke.
Neither is fixed here; a fix would be measured on a new held-out set (set 6 is now spent).
