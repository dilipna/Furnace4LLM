# Validation continuation — 2026-11-19

The integration remains a draft; no merge, deployment, billing or new GPU experiment.
The owner's test checkout and original ZIP remain unchanged.

## Corrected evidence defect

While reviewing `scripts/validate_managed_model.py` before another real-model trial,
the finalizer was found to write `result: passed` whenever the failed-check list was
empty, even if an exception or Ctrl+C aborted the procedure before it ran its checks.
The process still exited unsuccessfully, but the retained JSON falsely claimed success.

Reproduction: replace Studio startup with a raised `RuntimeError`, `SystemExit` or
`KeyboardInterrupt`, invoke the validator and read its saved JSON. All three regression
cases failed before the fix because the recorded result was `passed`.

The validator now starts with `completed: false`, records the exception type as a failure,
preserves the original exception/exit, and requires completed execution plus no failed
checks to record a pass. Exception messages are not copied into evidence because they can
contain private server data. The saved-report checker also rejects an explicit incomplete
record claiming success; historical records without the new field remain supported.

Verification: thirteen focused recorder/report tests pass; Ruff and formatting pass; saved
historical model evidence still passes `render_model_validation.py --check`. No historical
JSON, score, acceptance rule or threshold was changed.

## Execution evidence

At clean `85575fa38fc14200b6fbbc3515816ca1a7ba0f59`, a new ZIP passed native Windows
installation from a dedicated empty uv cache: metadata, edits, kit export, eight authored
HTTP requests, restart, token rotation and workspace release. Existing user and installed
Python 3.12/uv; this is **not a fresh profile**. Receipt:
[Windows empty cache](integration-verification/windows-empty-cache-85575fa.json).
ZIP SHA-256: `ed1a1697ebe102736438c90badff400cbb6e93123049190d0251dcf5c245a700`.
The owner's original ZIP was not replaced.

At clean `584e1b989a728500da2bec4d72b48f4f8bcbfb84`, Qwen2.5 0.5B Q8_0 ran through
the actual Studio-managed llama.cpp path on **CPU**, two threads, 2048 MiB container
limit, using pre-existing pinned images and weights. No model/image download or GPU
inference was required. All **33 operational checks passed**: real completion, evaluations,
repeat output identity (12/12), identity across server restart, injected server crash,
explicit recovery, hard Studio crash/orphan recovery, export and stop. Independent
post-trial Docker inspection confirmed zero trial-owned containers and networks.

The model passed **11/12 rule checks**, with its failed case retained. This is not semantic
quality, architecture certification, GPU evidence or a performance comparison. It covers
one small recipe on this Windows/Docker machine and does not establish concurrency or
long-running reliability. The complete source-bound [CPU record](integration-verification/real-model-qwen-cpu-584e1b9.json)
is checked in CI using `--records-only`; the older historical table is unchanged.

## Local Linux result and remaining limitation

The local full Python run at `85575fa` completed: **687 passed, 2 failed**. Lint, format,
types, import contracts and database migration passed. Both failures are real serving
tests timing out on `127.0.0.1` readiness; the second expected a load failure but received
a timeout. This is a failed run, not a pass, and it stops the script before Web/image.

A separate disposable HTTP probe reproduced the topology difference: the Windows host
received HTTP 200 at the Docker loopback-published port, while both a bridge-networked
Linux container and `--network host` returned connection refused. The local container
runner cannot observe the daemon host's loopback endpoint on this Docker Desktop setup.
The completed hosted Ubuntu suite runs on its host directly; it remains separate evidence.
No binding was widened, timeout increased, test skipped or global Docker setting changed
to hide the local failure. A native Linux host or separately approved/configured supported
host-network setup is still needed for a full local-script pass.

Remaining: actual human observations, fresh Windows profile/native file chooser review,
other hardware/operating systems and longer model runs. The CPU record closes the bounded
current-build CPU journey for this recipe, not those broader gates. Keep the PR draft and
unmerged; cloud service, billing, installers and deployment remain outside this work.
