# Document protection, recovery, chunking and questions

Local source trials on November 25, 2026; not a release, installed acceptance or a
human pilot. The owner selected **Qwen3-4B for compatible NVIDIA GPUs** and
**Qwen2.5-1.5B for CPU/faster use**. Main is unchanged. Older scores and failed trials
remain separate. The latest full installed 36-case result is still 31/36 and 7/8
attacks on source 04ef0a0; do not replace it with the focused source results here.

[Derived tables and input hashes](verification/everyday/document-improvements-summary.json)
link every raw record. Reproduce without inference:

```powershell
uv run python scripts/report_document_improvements.py --out dist/document-improvements-reproduced.json
```

The script refuses overwrites, verifies suite identities and keeps failed executions
in planned denominators. These individual runs share one Windows 11/Docker Desktop
machine, about 8 GB Docker memory and an RTX 3050 Ti 4 GB. Models ran sequentially;
developer activity also occurred. Timings are observations, not controlled speedups.
Some records explicitly report a dirty source tree. None is relabelled as an installer
or a measurement of a later documentation head. Random delimiter nonces were not saved;
exact prompt replay remains unavailable.

## 1. Set aside AI-directed sentences

The existing detector now removes flagged sentences, and some command continuations,
before inference by default. The UI shows the exact set-aside text, count, **Show**
and **Include it anyway**. Opt-in text remains marked. Clear/workspace changes erase
the displayed set-aside text too. This is a heuristic, not a sandbox.

Same eight fixed attacks, unchanged rules:

| Default | Earlier source comparison | Fresh pre-change baseline | New path: include flagged text | New path: set aside |
| --- | --- | --- | --- | --- |
| Qwen2.5-1.5B CPU | 2/8 | 1/8 | 0/8 | **8/8** |
| Qwen3-4B GPU | 8/8 | 8/8 | 8/8 | **8/8** |

The paired new-path runs differ in the explicit include flag. The different CPU
pre-change result is retained, not averaged away. One run passing eight known attacks
does not establish general resistance or protection against all documents/languages.
An instruction embedded in a factual sentence may also remove the fact.

The deterministic output check warns about numeric/date strings appearing only in
flagged text. All eight CPU opt-in outputs triggered the stronger warning; the
set-aside outputs did not. It is a literal provenance check, not an arithmetic or
semantic validator; reformatting numbers/dates can evade it.

**False positives:** 0/34 author-labelled non-attack suite inputs were flagged.
Separately, 3/5 deliberately chosen benign AI-documentation controls were flagged:
a manual mentioning a system prompt, a quoted research instruction and a USER column
label. All five controls are in the derived report. This is not a customer false-positive
rate. Inspectable removal and opt-in are necessary; do not advertise the detector as exact.

## 2. Recover after request timeout

The transport already shut down its socket at the deadline. The defect was persisted
connection state: a timeout marked the whole connection failed, and later requests
were refused before executing. Recovery now health-checks the same approved
configuration and advertised model ID before the next request. It does not replay the
failed prompt, restart a server or override changed configuration/explicit disconnect.

| Check | Before | After |
| --- | --- | --- |
| Slow HTTP adapter | Socket cancellation observed; first follow-up refused with 409 | Socket cancellation observed; four follow-ups actually execute and state is connected |
| Original Qwen3 CPU trial | 120-second timeout; four subsequent requests refused | Exact 120-second scenario not rerun |
| Real Qwen2.5-1.5B CPU probe | Same uncancelled control takes 18.828 s | Long request cancelled at 2.047 s; four follow-ups return 4 in 265, 78, 125 and 110 ms of endpoint time |

The real probe uses an explicitly configured **two-second** deadline, not a changed
benchmark threshold. It checks the pinned single-slot server through the actual
relay. It does not instrument llama.cpp internals or establish recovery from an OOM.
Regression tests additionally refuse recovery after disconnect, configuration change
or wrong advertised model. Historical interrupted evaluations still require their
existing explicit retry; no incomplete evaluation is silently labelled successful.

```powershell
uv run pytest -q apps/api/tests/test_studio_model.py -k timeout
# Real model/Docker, explicit local preparation/start; refuses an existing output:
uv run python scripts/verify_timeout_recovery.py --out dist/timeout-probe.json
```

Raw evidence: [real probe](verification/everyday/real-timeout-recovery.json).

## 3. Context-derived chunks

The budget reserves actual prompt/system bytes, output tokens and 256 tokens for the
chat template. Remaining UTF-8 bytes bound fallback tokenization conservatively.
It uses more of the selected context than the fixed 1,000-byte limit, without claiming
an exact token count. Summaries retain staged processing; no timeout/output limit changed.

The exact same PDF hash, 25 text pages and 66,380 extracted UTF-8 bytes:

| Device | Sections before → after | Model requests before → after | Answer seconds before → after | Rule result |
| --- | --- | --- | --- | --- |
| CPU, Qwen2.5-1.5B | 67 → 33 | 75 → 36 | 223.360 → **197.000** | Both required fields pass in both runs |
| GPU, Qwen2.5-1.5B | 67 → 33 | 75 → 36 | 78.000 → **49.437** | Both required fields pass in both runs |

Parsing was separate: CPU 0.546 → 0.532 s, GPU 0.609 → 0.766 s. Task times exclude
parsing, preparation and loading. These are not repeated controlled trials or a full
document-fidelity assessment. Scanned PDFs still need unimplemented OCR.

A staged UI request now shows a planning range before starting and lets the user
decline without sending the document to the model. It is a broad CPU/GPU heuristic,
not calibrated to every machine. Streamed elapsed/request observations refine it.

## 4. Retrieve original evidence for long questions

Six new long Q&A cases retain original facts/rules and add administrative background.
They are included in the 42-case packaged suite. The focused trial uses the exact
archived six-case requests, not a new full 42-case acceptance score.

Dependency-free BM25 selects up to three bounded original sections. When fewer than
three match, adjacent context fills unused slots. Sources are displayed separately
from the answer, so numeric answer formats remain intact. References identify text
provided to the model; they do not certify that every claim follows from it.

| Default | Before: passes / 6 | First retrieval: passes / 6 | Corrected retrieval: passes / 6 | Median completed seconds before → final | Completed model requests before → final |
| --- | --- | --- | --- | --- | --- |
| Qwen2.5-1.5B CPU | 5/6 | 5/6 | **6/6** | 48.719 → 6.961 | 93 → 6 |
| Qwen3-4B GPU | 4/6 | 3/6 | **6/6** | 25.984* → 2.875 | 76* → 6 |

*GPU baseline completed five tasks: one rule failure and one **OOM-killed container**
remain failures in the six planned tasks. Median/request totals cover completed tasks
only. The recorded container had exit 137 and OOMKilled=true; this is distinct from
the earlier CPU timeout.

The first CPU retrieval missed form facts beside the matching section. A failing
boundary regression led to adjacent-context retrieval. In the first GPU retrieval,
three numerically correct answers failed the existing rules because generated numbered
citations introduced extra numbers. The corrected prompt leaves source references to
the app and follows the requested answer format. No numbers were stripped from outputs,
no scoring rules changed, and both unsuccessful trials remain archived.

Limits: lexical queries can miss paraphrases; three source sections cannot cover
every multi-part question. Summaries still lose context. The latest focused result is
not semantic quality or a guarantee on new user documents. Model/runtime memory fit
remains conditional.

## Verification and release gates

API tests assert actual sent messages, omission/opt-in of flagged text, output warnings,
context bounds, source offsets, refusal and lack of document persistence. Browser
automation exercises the real local API with a deterministic adapter: preflight,
estimate/decline, source references, set-aside inspection/opt-in, clear/navigation,
mobile and no external requests. It is not model inference or human comprehension.

Owner walkthrough observations, clean-account install/keep/delete, independent pilot,
quality acceptance and integrated-source packaging remain gates. Original November 24
walkthrough materials and port 4010 are untouched. No release, deployment, PR readiness
or main merge is authorized by these measurements.
