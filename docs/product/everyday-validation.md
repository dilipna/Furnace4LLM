# Everyday-model evidence

## Historical installed outputs and separate v3 re-scoring

The original records below are unchanged. Re-scoring existing outputs is not new inference.

| Saved outputs | Original v2 rules | v3 with original rules | v3 with revised everyday rules |
| --- | --- | --- | --- |
| CPU | 5 pass / 4 fail / 2 unscored | 6 / 3 / 2 | 9 / 2 / 0 |
| NVIDIA | 5 pass / 4 fail / 2 unscored | 5 / 4 / 2 | 8 / 3 / 0 |

Only the punctuation change is a scorer correction: surrounding inverted Spanish
punctuation is now stripped, while English “Good morning.” still fails Spanish translation.
The suite separately accepts a deadline within a sentence and adds fixed missing-info/reply
rules. Those rules check an admission or required text plus specific forbidden time forms;
they do not establish semantic correctness or detect every possible invented commitment.
The [re-score record](verification/everyday/rescore-v3-revised-suite.json) records original
file hashes, old scores, the revised rules and new verdicts. The preliminary v3 record
is also retained. The original suite and exact baseline suite bytes are archived.

## Original installed v2 trial results

Candidate: Qwen2.5-1.5B Instruct Q4_K_M, Apache-2.0, pinned revision and SHA-256
in the catalog. Installed source `2c250d642a1af2b648b67cb34fd190f535f24d8a`.
These trials do not verify every later build or establish semantic quality.

| Trial | Operational completion | Rule checks | Unscored | Median end-to-end task latency | Observed range |
| --- | --- | --- | --- | --- | --- |
| CPU | 11/11 | 5/9 pass, 4 fail | 2 | 2.500 s | 1.469–10.453 s |
| NVIDIA recipe | 11/11 | 5/9 pass, 4 fail | 2 | 1.781 s | 1.313–5.875 s |

These are individual runs, not a controlled speedup study. Task latency includes local
HTTP, Docker privacy observations and staged processing; it excludes file extraction,
model download and loading. The raw records include per-task latency, request usage,
actual outputs, recipe, Docker allocation and the 4 GiB container request.

Failures remain: the date question included extra prose despite its exact-format rule;
simplification reformatted the date; Spanish punctuation differed from the normalized
expectation. Most seriously, the document-instruction case returned the injected amount
1000 instead of the real invoice total 95. This is a genuine answer/instruction-following
failure. Network isolation is not a prompt-injection or factual-accuracy guarantee.
Missing-information and reply-quality cases remain unscored for human review.

The first GPU attempt failed before inference because Docker was unavailable. It is
retained separately. No model rule, threshold or unfavorable result was removed.

Raw records: [CPU](verification/everyday/everyday-qwen-1.5b-cpu-2c250d6.json),
[NVIDIA](verification/everyday/everyday-qwen-1.5b-gpu-2c250d6-retry.json),
[unavailable Docker](verification/everyday/everyday-gpu-docker-unavailable.json).

The later word-boundary regression fix has unit coverage, but these installed trials
belong to the earlier 2c250d6 candidate. Fresh selected-release acceptance remains a gate.
The model remains a quality-review candidate; it is not approved here for sensitive
professional decisions. Owner/pilot comprehension and quality observations remain blank.


## Reproduce the recorded document journey

The real recording uses the installed, unsigned Windows 2c250d6 candidate, Microsoft
Edge at its standard Program Files (x86) path, Docker Desktop Linux containers, the
pinned NVIDIA recipe and a working NVIDIA GPU. Preparation/download and start occur
before the uncut footage; the synthetic invoice is not customer material. This is
an automated recording, not a human comprehension test. It is not a CPU recorder.

From this checkout, after installing the selected app in a disposable test location:

```powershell
uv sync --frozen
uv run python scripts/record_everyday.py --app C:\path\to\installed\Furnace --out dist/real-document-recording
```

`--app` must contain build.json and runtime/python.exe from the actual installed app.
The command creates its own temporary workspace, explicitly prepares/starts the model,
records actual requests, then quits and checks lease release. It can download model
weights to the shared cache; it does not publish anything. Keep generated media local.
The [recorded receipt](verification/everyday/document-recording-2c250d6.json) preserves
build identity, actual answer, observed isolation and clean quit. It is not verification
of a later installer merely because this command is documented.
