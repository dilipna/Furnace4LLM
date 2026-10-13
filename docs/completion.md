# Completion checklist (2026-10-13)

Replaces the claim "only two things remain" (the 2026-10-13 00:37 UTC handoff message said
"Two things are still open": the gate validation and the live GitHub run). That was wrong:
it left out the optimizer measurement, judge calibration, deployment, the second fixture and
the scope decisions, all of which are acceptance criteria in the plan or in `docs/scope.md`.
Every unfinished criterion is listed below. Status words: **done**, **running**, **not
started**, **blocked on the owner**. Nothing here is marked done without a result file.

## A. Perf gate (frozen rule, `docs/gate-revision.md`)

| criterion | status | evidence / what is left |
|---|---|---|
| Rule frozen before implementation; thresholds unchanged | done | 6e90c99 (design) before 26fa8eb (code) |
| V1 unchanged code, 24 counted trials | running | 11 counted + 3 affected (6, 9, 10: kept, replaced) of 24; rule in `bench/results/2026-10-12-gate-validation/NOTES.md` |
| V2 restored baseline, 12 trials | running (queued) | same run |
| V3a R1 (+800%), V3b R2 (+30%), V3c depth 4 / 8 (+13%, +18%), 6 trials each | running (queued) | known sizes fixed in 9d80db8 before any trial |
| Report: verdicts recomputed from raw samples, old rule on the same data, targets met / not met | built; final after the run | `validation/report.md`; tail latency (p95) in its own advisory table; rationale for the metric, interval and thresholds; latency-location limitation kept |
| V4 repair (RQ5) under the frozen gate, 3 attempts | running (queued) | reported as measured, not a gate criterion |

## B. Optimizer

| criterion | status | evidence / what is left |
|---|---|---|
| Quality-constrained grid (8 configs), frozen criteria | running (queued after the gate) | `docs/optimizer.md`; `bench/results/2026-10-12-optimizer/optimizer/` |
| Independent rerun of the selected config against the baseline | running (queued after the grid) | rules fixed before the grid (A B B A A B B A, new seeds); outcome may be "no improvement" or "inconclusive" and is reported as such |

## C. Scanner and Guard

| criterion | status | evidence / what is left |
|---|---|---|
| Frozen scanner on fresh Python apps (set 6, chosen by a fixed search) | finding correctness and citations done; call sites after the GPU run | labels `ebd5824` before the scan; `bench/results/2026-10-13-set6/set6/` |
| Finding correctness, separate from citation validity and call-site P/R | done | findings P 39/77, R 39/64; citations 148/148; call sites: RQ1 after the GPU run |
| Post-hoc review of every set-6 disagreement (beside the result, never folded in) | not started | after RQ1 |
| Uncertain / unsupported analysis widens the checks | done | six gaps found by tests and fixed (41ca529); RQ3 and set-4 selections unchanged; `2026-10-13-fallback/NOTES.md` |
| Second fixture (Python, F2 `agent-actions-py`) | built; not yet run | Scan (RQ1 F2 column), Guard R4, tests in `test_f2_fixture.py`: after the GPU run |

## D. GitHub workflow (real)

| criterion | status | what is left |
|---|---|---|
| GitHub App with only the manifest's permissions, installed on `furnace-demo-f1` only | blocked on the owner | create the public repo, run `furnace gh-setup`, click Create, install |
| Live run: Forge draft PR, Guard check run, repair draft PR; PR links, commit SHAs, webhook HMAC verification, redelivery no-op, forged request refused, check-run outcomes | blocked (needs the App) | `scripts/live_github_run.py`, `scripts/live_github_verify.py` are ready |

## E. Judge calibration (RQ2)

| criterion | status | what is left |
|---|---|---|
| 60 human labels (grounded / correct) | blocked on the owner | `/evals` or `bench/label.py`; ~1.5 h |
| `ungrounded_answer` judge run and calibrated (TPR, TNR on the held-out test split) | blocked (labels + a Groq key) | one run after the labels exist |

What the 60 labels are for: they are the only human ground truth in RQ2. They measure (a)
how well the cheap deterministic citation check predicts "grounded" on real answers, and (b)
whether the LLM judge can be trusted (only if its TPR and TNR against the human labels are
both >= 0.8; its failure rates on unlabeled data are then corrected with Rogan-Gladen). How independence is kept: the owner labels, not the developer agent; both
labeling screens show question, context, documented answer and model answer only (no check
or judge verdict); the label file is committed before the judge runs; a fixed split (seed 0)
puts 12 items in train (the only source of few-shot examples), 24 in dev (the only place a
judge prompt may be adjusted) and 24 in test, reported once and never used to change the
prompt. With 24 test items the intervals are wide, and the count of ungrounded items is
reported with them.

## F. Deployment

| criterion | status | what is left |
|---|---|---|
| Hosted control plane (Vercel, Render, Supabase) | blocked on the owner | accounts, or a decision to take it out of the MVP |

## G. Scope (signed off 2026-10-13)

Python only; TypeScript and VLM deferred; rule-based repair for the documented case; the
second fixture kept as Python (`docs/scope.md`).

## H. Claims

| criterion | status | what is left |
|---|---|---|
| Every website and resume number traced to dataset, commit, gate version, raw results; no old-gate result combined with a new-gate claim | in progress | `docs/claims.md`; landing tiles fixed (a tuned-set call-site figure was shown as held-out); resume: no Furnace claims found yet |
