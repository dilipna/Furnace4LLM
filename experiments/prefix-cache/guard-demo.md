# From a measured cache failure to a regression test

The serving benchmark asks what happened to latency. This CPU-only rehearsal asks
whether Furnace's existing Forge-installed prefix test catches that prompt-layout change.
It is a different check on the same saved workload, not another serving benchmark.

## Run in under a minute

From the repository root, Python 3.12 with only its standard library:

```bash
python experiments/prefix-cache/rehearse_guard.py
```

The script reads the literal `PREFIX_TEST` from
[`furnace/forge/templates.py`](../../packages/furnace/src/furnace/forge/templates.py),
fills its normal questions and threshold, then runs the generated test in a subprocess.
Its harness only returns the recorded JSON messages; it does not contact a model.
The original test's assertions are unchanged. A small footer reports the observation
and invokes the test function directly, so pytest is not required for the rehearsal.

## Observed structural outcomes

Recorded October 19, 2026, against all 60 questions in each of the three repeats:

| Condition | Minimum shared leading characters | Required | Forge test | Meaning |
|---|---:|---:|---|---|
| A: stable, cache on | 8839 | 7955 | PASS, 3/3 | Baseline control |
| B: stable, cache off | 8839 | 7955 | PASS, 3/3 | Server setting is invisible to a text-only test |
| C: metadata first | 15 | 7955 | FAIL, 3/3 | The recorded regression is detected |
| D: metadata last | 8831 | 7955 | PASS, 3/3 | Shared leading text is retained |

The current Forge threshold is 90% of the baseline shared characters, rounded down.
Role labels and separators are included, as in Forge's implementation. These are text
character counts, not token counts or cache-hit measurements. See the machine-readable
[replay observations](guard-replay.json), including the template hash and real exit codes.

The overall rehearsal succeeds when each known condition has its expected result.
C failing is intentional; its generated test process actually returns exit code 1.
An unexpected outcome makes the rehearsal return nonzero.

## Use it on a candidate change

Prepare rendered prompts for the same questions on base and head as JSONL, then run:

```bash
python experiments/prefix-cache/rehearse_guard.py --base base.jsonl --head head.jsonl --json prefix-check.json
```

The candidate command returns 0 for a structural pass, 1 for a regression and 2 for
invalid inputs or execution errors. Duplicate or mismatched questions, non-text messages
and baselines with no useful shared leading text are refused. It replays only data;
snapshot creation must use the application's own rendering path separately.

For a local demonstration using this repository's recorded payloads, substitute:

```text
base.jsonl = experiments/prefix-cache/runs/2026-10-19-small-model-v2/r1-A-attempt1/workload.jsonl
head.jsonl = experiments/prefix-cache/runs/2026-10-19-small-model-v2/r1-C-attempt2/workload.jsonl
```

The C candidate returns 1. Replacing it with `r1-D-attempt1/workload.jsonl` returns 0.
These payloads are synthetic; using them does not establish performance on your app.

## What to explain in a technical interview

“A request ID at the start of a shared prompt removed reuse in my controlled vLLM
benchmark. I reused Furnace's actual generated test to catch the structural change
without requiring a GPU in every CI run. The test rejected all three bad-layout
snapshots and accepted the metadata-last ones. It also passed the cache-disabled
control, which shows why I still need serving-configuration and measured-latency checks.”

Only use this explanation if you can walk through the code and its limitations. No
new latency result, answer-quality result, production deployment or external user is
claimed by this rehearsal. The existing GPU benchmark and regression gate remain
separate sources of evidence.
