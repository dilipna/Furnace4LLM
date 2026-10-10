# RQ1 on 2026-10-09: SDK coverage and script workflows

Order of work (visible in git history):
1. `bench/ground_truth/*` for **held-out set 3** (Gemini via LangChain, Mistral, Replicate, Bedrock
   via LangChain, Cohere with an injected client) labeled from source at pinned commits and
   committed before any scan (129103c).
2. Baseline with the unchanged scanner: `rq1_set3_baseline.md` (7fe8c79).
3. Scanner change (SDK client classes by import origin, client-typed inference methods incl.
   injected `self.<attr>` clients and executor-submitted methods, module-function APIs with an
   implicit endpoint, more LangChain model wrappers, Streamlit/CLI entrypoint workflows),
   designed from the SDKs' documented APIs and tested on synthetic programs.
4. A scorer bug found while reading set-3 results: `_split_key` cut a qualified name at the first
   dot, so a call site in a class method (`Bot.reply`) could never match its label. Fixed and
   re-scored on **both** scanners: `rq1_old_scanner_rescored.md` (scanner at 7fe8c79, fixed scorer)
   vs `rq1.md` (new scanner).

| LLM call sites (P / R) | set 1 (held-out) | set 2 (seen since 10-06, now dev) | set 3 (held-out) |
|---|---|---|---|
| old scanner | 1.00 / 1.00 (8/8) | 1.00 / 0.20 (1/5) | 1.00 / 0.11 (1/9) |
| new scanner | 1.00 / 1.00 (8/8) | 1.00 / 1.00 (5/5) | 1.00 / 0.89 (8/9) |

Workflows: set 1 0/9 -> 6/9, set 2 1/5 -> 4/5, set 3 0/9 -> 6/9 (precision 1.00 throughout).
Serving engines, set 3: 0/5 -> 4/5. Models, set 3: 1/17 -> 3/17 (ids in YAML/JSON configs and
selectboxes are not read). Set 1 and the dev fixture are unchanged elsewhere: no regressions.

Still missed on set 3: a LangChain model stored on `self.llm` and piped into a runnable
(Bedrock main app); `cli:` index-building scripts (no query-time LLM or retrieval, by design);
model ids from config files; prompts in JSON persona files; README entrypoint contradictions.
Labels by the developer agent, not independently reviewed.

Post-hoc fix, disclosed: reading the llamav2-chat (set 3) Blueprint showed "retries: tenacity"
claimed from a pinned transitive dependency the code never imports. A retry library now counts
only when the code imports it. Effect: set-3 attribute accuracy 61/63 -> 62/63; nothing else
changed. Because the fix was found on set 3, that one attribute is not a held-out result.
