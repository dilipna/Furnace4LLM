# Hosted concurrency failure — 2026-11-17

PR #12's first hosted Python run at `23ce21c` failed:
[CI job](https://github.com/dilipna/Furnace4LLM/actions/runs/44163919240/job/134324762191).
Result: 618 passed, one skipped, one failed. Web, API image and saved evidence passed.
This was not the earlier local timing failure or the new shutdown regression.

The failed test was the existing real-Docker two-initializer publication test.
After creation, one initializer could not inspect a completed reference and raised
`dependency cache publication could not be confirmed`. The original implementation
discarded the create result, so the hosted log cannot establish its exact failure
reason. No claim that the hosted root cause is fully proven is made here.

Inspection found a missing concurrency case: a competing initializer can encounter
a name conflict before the winning reference is visible. A deterministic scheduling
regression models exactly that state, with a complete winning volume appearing on
the third probe. Against the exact old `prepare` function loaded from Git, it failed
at the same unconfirmed-publication check. After bounded confirmation it passes,
selects the winning complete volume, cleans only its own candidate and installs once.

The correction is a distinct commit because it blocks the otherwise scoped UI PR.
Its confirmation polling deadline starts with the existing 30-second create phase;
individual Docker calls retain their existing per-call limits. This is not a new
hard wall-clock guarantee for all Docker operations.
Each selected reference still passes the same image, key, read-only mount and marker
validation. It never accepts a partial volume, mutates the winning cache, retries pip
or changes installation/evaluation acceptance. If publication never appears, a second
test requires a bounded failure that includes the original create exit/error and
preserves its ambiguous candidate. All ten cache orchestration tests passed locally.

The existing real-Docker concurrency test remains unchanged. Fresh full local and
hosted checks on the corrected head are required; the failed hosted run remains
part of the evidence. There is no rerun of the unchanged failed head to obtain green.

The rebuilt application at `944f5232ae4747563c9b99e6da7ec4c66a8aec1d` passed
Windows warm-cache and Linux initially empty-cache installed journeys, including
eight/18 authored HTTP requests respectively, restart and lease/listener cleanup.
The Linux run included Chromium browser identity/import/history/export checks.
ZIP SHA-256: `4485aad81a494ca6aa15beccb6fe6b04b227939808cc098c7c8ad9d47ef59da2`.
[Windows receipt](evidence/944f523-installed-windows.json) ·
[Linux receipt](evidence/944f523-installed-linux.json).
These application journeys do not replace the existing real-Docker publication
test or fresh exact-head hosted checks. No model inference was performed here.

Separately, concurrent [PR #11](https://github.com/dilipna/Furnace4LLM/pull/11)
proposes managed-model functionality and validation receipts. It was not modified
or validated here. Confirmed overlapping paths include `studio.py`, `model.html`,
`model.js` and `studio.js`; merge conflicts and the model claims still need review.
