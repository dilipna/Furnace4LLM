# Held-out set 6: protocol, fixed before any app is chosen (2026-10-13)

Purpose: measure the scanner as it is now on Python LLM applications it has never seen, with
three quantities kept apart: whether it finds the LLM call sites (call-site precision and
recall), whether the Blueprint findings it emits are true and complete (finding correctness),
and whether each finding's evidence links resolve (citation validity). Earlier sets were
partly chosen to probe a construct (set 5 for the Agents SDK); this set is chosen by a fixed
procedure instead.

## 1. Frozen scanner

Scanner = `packages/furnace/src/furnace/{code_intel,reconstruction,blueprint}` at commit
**41ca529**. No change to those paths until every set-6 number below is recorded. A change
made afterwards is measured on a later set, never on this one.

## 2. App selection (mechanical)

One GitHub search, run once, its raw response saved as
`bench/results/2026-10-13-set6/search.json`:

    GET https://api.github.com/search/repositories
        ?q=llm app language:python stars:20..3000 pushed:>2025-06-01
        &sort=stars&order=desc&per_page=100

Walk the results in order and take the **first 5** repositories that meet every inclusion
rule; record each skipped repository with the rule it failed (`selection.md`).

1. An application (web server, Streamlit/Gradio app, bot, CLI or agent service), not a
   library, SDK, framework, model, dataset, prompt collection, course or list.
2. Its Python code makes at least one LLM generation call (embedding-only does not count).
3. Python is the main source language, with 3 to 60 non-test Python files.
4. Not an app of sets 1-5, and not owned by an owner of any app in sets 1-5.
5. The default branch can be cloned; the commit is pinned at selection time.

Rules 1-3 are decided from the repository's file list and source, never from Furnace output.

## 3. Labels, written and committed before the first scan

One `bench/ground_truth/<app>.yaml` per app (`split: held-out-6`), same schema as sets 1-5
(call sites, routes, models, engines, retrievers, tools, prompts, workflows, existing
reliability, contradictions), plus `expected_findings`: the Blueprint findings that should
be emitted for this app at the pinned commit, derived by hand from the source and from the
rule definitions in `blueprint/rules.py` at 41ca529:

| rule | expected when (from the labels) | unit |
|---|---|---|
| sec.tool_approval_boundary | a tool with a write/external side effect and no approval gate | per tool |
| sec.approval_gate_regression_test | a tool with an approval gate | per tool |
| rel.llm_timeout | some LLM call site has no timeout (call or client) | app |
| rel.fallback_gateway | LLM calls, no retry policy and no fallback endpoint | app |
| eval.citation_contract | RAG present and a prompt instructs the model to cite sources | app |
| eval.grounding_judge | RAG present | app |
| eval.regression_suite | LLM calls and no eval framework or eval dataset | app |
| obs.genai_tracing | LLM calls and no tracing library (custom logging does not count) | app |
| obs.prompt_versioning | a prompt written as a string literal in Python source | per prompt |
| inf.prefix_instability | a system message that starts with per-request values before static text | per message |
| inf.prefix_stability_guard | a system message with a static prefix of >= 2,048 characters, not dynamic-head | per message |
| inf.prefix_caching_disabled | a vLLM serving config with prefix caching turned off | per config |
| inf.context_budget_gate | a system message and a configured retrieval-context size limit in characters | app |
| inf.serving_baseline | the app is served by a self-hosted engine (vLLM, SGLang, Ollama, TGI) | app |

Labels are written by the developer agent (Claude) from source and are **not independent**;
they are committed before the scan so the scan cannot influence them.

## 4. Metrics, each reported on its own

- **Call sites** (RQ1 matching rules, unchanged): precision and recall with counts.
- **Finding correctness.** A predicted finding is (rule, item); item = the tool, prompt or
  message for per-item rules (matched by file and line overlap with the labeled item, or by
  name), "app" otherwise. Finding precision = predicted findings that are expected /
  predicted; finding recall = expected findings that were predicted / expected. Counts and
  denominators always shown, per rule family and pooled.
- **Citation validity** (`bench/external_validation.py`, unchanged check): share of evidence
  items whose file exists and whose line range contains the excerpt. It says nothing about
  whether the finding is right.

These three are never combined into one score.

## 5. After scoring

The numbers computed against the committed labels are the result and are not replaced.
Afterwards every disagreement (a missed or an unexpected finding or call site) is reviewed
and listed with a note saying whether the label or the scanner was wrong; that review is
reported beside the result, never folded into it. With 5 apps, intervals are wide and are
reported (exact binomial).

## 6. Addendum before the first scan (2026-10-13): definitions fixed while labeling

Written after the apps were read and before Furnace ran on any of them.

- **LLM call site**: a direct text-generation request in non-test Python (SDK call, agent-SDK
  run, or a raw HTTP chat request); calls made through a wrapper are labeled where the request
  is made. TTS, embedding and CLI-subprocess calls are not LLM call sites.
- **Prompt**: a system message, agent instructions, or a named prompt constant (module or
  class level, name containing "prompt", "instruction" or "system"); user-message f-strings
  built inside a function are not prompts. `obs.prompt_versioning` is expected per such
  prompt written as a string literal in Python.
- **Dynamic head**: a system message whose first per-request value comes before more than
  half of its static text. Values fixed per deployment (e.g. an env-configured token) and
  per conversation (character name) are not per-request.
- **Scope cut, declared now**: Soul-of-Waifu (about 67,000 lines; system messages assembled
  from user templates, character cards, world state and memory) is labeled for call sites,
  routes, existing reliability and app-level findings only; its other categories and per-item
  findings are `not_labeled` and scored as nothing. BYO-LLM-WIKI does not label workflows.
- **Scoring code, fixed now** (`bench/rq1.py`, `bench/set6_findings.py`, tested in
  `bench/tests/test_set6_findings.py`): `not_labeled` categories and `not_labeled_findings`
  rules count on neither side; a workflow label `<kind>:<file>.py` (cli, streamlit, gradio)
  matches a predicted workflow whose key contains the file, as `cli:`/`streamlit:` already did.
