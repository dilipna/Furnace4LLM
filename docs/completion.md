# Final acceptance checklist (release of 2026-10-13)

Furnace is released as a bounded portfolio project: Python only, fixtures F1 and F2,
rule-based repair for one regression family, scanner findings advisory, no hosted
deployment. Status words: **verified** (a result file shows it), **failed** (measured and
did not hold), **inconclusive** (measured; the data cannot decide), **deferred** (out of this
release by a recorded decision), **blocked** (needs an action only the owner can take).
Nothing is marked verified without a file. This replaces the progress checklist of the same
name (history in git).

## A. Perf gate (G3, frozen in `docs/gate-revision.md` 6e90c99, implemented 26fa8eb)

| criterion | status | evidence |
|---|---|---|
| Design frozen before implementation and validation; thresholds never changed | verified | commits 6e90c99 → 26fa8eb → trials |
| Unchanged code (V1 24 + V2 12 = 36, planned in 6e90c99): false FAIL ≤ 10%, PASS ≥ 70% | verified | 0/36 FAIL (95% CI 0-9.7%), PASS 29/36; V1 18/24, V2 11/12 (`2026-10-12-gate-validation/validation/report.md`) |
| Every unchanged-code outcome listed, incl. the 7 not PASS | verified | all 7 INCONCLUSIVE, none FAIL (`NOTES.md` "Reconciliation", `validation/trials.md`) |
| Trial count reconciled (63 recorded = 60 counted + 3 affected and replaced) | verified | `validation/trials.md` |
| GPU clock: configured condition vs observed | verified | condition 780 ± 80 MHz under a probe load; observed 780-828 MHz over 378 runs; unchanged-code trials all at 780 (`NOTES.md`) |
| Known large regression (R1) blocked | verified | BLOCK 6/6, +609% to +621% |
| Detection of regressions just above the 10% tolerance | **inconclusive** | graded changes calibrated at +13/+18/+30% measured +4 to +7% in the gate; INCONCLUSIVE 15/18, PASS 3/18 |
| Tail-latency (p95) regressions | not claimed | p95 is advisory by design; a latency-location gate |

## B. Repair (rule-based, one supported scenario)

| criterion | status | evidence |
|---|---|---|
| Regression test fails on PR, passes on base, before any fix | verified 3/3 | `2026-10-12-gate-validation/rq5.md` |
| Repair accepted by the frozen gate (F1, R1; 3 repeated trials of one scenario) | verified 3/3 | +4.2% / +0.9% / +1.7% vs main, 90% upper bounds 9.5 / 4.1 / 7.2; measured at 6efebfd, 780 MHz, AC |
| First strategy rejected, kept in the record | verified | INCONCLUSIVE once, BLOCK +37.8% and +39.6% |
| Repaired prompts equal the base revision's | verified | 34/34 questions byte-identical in each attempt (`rq5/prompt_identity.md`) |
| Moved value is diagnostic and not sensitive (this scenario) | verified | random 8-hex id + UTC time; the repair PR now warns that logged values are not inspected (`NOTES.md`) |
| Full-suite audit of the repaired tree | verified, with limits | every executed check passed 3/3; judge skipped (optional under the acceptance rule); the citation check sits at its 0/34 floor and cannot see a quality change |
| Unsupported regression (R2) refused, not guessed | verified | `rq5/r2_context_bloat_r0.json` |
| Interrupted attempt (AC lost) kept, not counted | verified | `rq5/discarded/` |
| LLM-patch strategy | deferred (D2) | `docs/scope.md` |

## C. Optimizer (rules fixed before the grid, `docs/optimizer.md`)

| criterion | status | evidence |
|---|---|---|
| Quality-constrained grid, 8 configs | verified | recommendation: keep the baseline (`2026-10-12-optimizer/NOTES.md`) |
| Independent confirmation of the selected config | **inconclusive** | goodput +3.8%, 90% CI -8.8 to +18.2; no improvement claimed |

## D. Scanner, Guard, fixtures

| criterion | status | evidence |
|---|---|---|
| Held-out set 6 (frozen scanner, labels first): call sites | verified (measured) | 32/48 found, 32/32 correct |
| Held-out set 6: Blueprint finding precision / recall | **failed** as a quality bar (no target was set) | precision 39/77, recall 39/64; findings are advisory |
| Held-out first-scan call-site recall, sets 1-5 | **failed** as a quality bar | 4/34 (`2026-10-12-reconcile/`) |
| Tool approval-boundary rule | **failed** on set 6 (28 of 38 false findings), now experimental | still runs and is stored; out of the default Blueprint and counts (`blueprint/rules.py::EXPERIMENTAL`, test in `test_f2_fixture.py`); set-6 results unchanged |
| Second fixture F2 (Python): Scan + Guard R4 | verified locally | `2026-10-13-f2/`; its text contradiction was missed (failed) |
| Guard targeted selection (RQ3) | verified, older gate (G0) | 46% of checks, 3/3 failures caught, 13/13 same conclusion (`2026-10-06/rq3.md`) |

## E. Real GitHub workflow

| criterion | status | what is left |
|---|---|---|
| App with the manifest's permissions, installed on `furnace-demo-f1` only | **blocked** | owner: create the public repo and run `furnace gh-setup` (`docs/github-app.md`) |
| Live Forge PR, Guard check run, repair draft PR; URLs, SHAs, check results, webhook checks | **blocked** | `scripts/live_github_run.py`, `scripts/live_github_verify.py` ready; mock-tested only; not claimed |

## F. Deferred by decision

| item | status | decision |
|---|---|---|
| Hosted control plane (Vercel / Render / Supabase) | deferred | D3, owner-approved 2026-10-13 |
| LLM-judge calibration (60 labels, TPR/TNR) | deferred | D4: no released claim depends on the judge (Guard's judge item always SKIPs; repair acceptance excludes it; product copy narrowed to "judge spec (uncalibrated)") |
| TypeScript, VLM, free-text evidence | deferred | D1 |

## G. Release steps

| step | status | evidence |
|---|---|---|
| Experiments finished under the frozen protocol, negative results kept | verified | RQ5 and optimizer as above |
| Documentation committed | verified | 34aa551 (results), baa02a2 and the final commit (docs, copy) |
| Required checks on the final commit (`poe check`, web lint/tsc/build) | pending | |
| One end-to-end rehearsal (`scripts/rehearse.py`) | verified (local path only) | 2026-10-13 at baa02a2: 6/6 steps, no page errors; Guard flagged R1 (`docs/demo.md` rehearsal record). The GitHub steps are not covered (blocked, E) |
| Three-minute demo script | verified | `docs/demo-3min.md` |
| Demo recording | verified (silent, local path) | `docs/demo-video/demo-2026-10-13-1537.webm` (git-ignored); a narrated three-minute take is the owner's |
| Case study | verified | `docs/case-study.md` |
