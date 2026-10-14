# Claims ledger: every public number, traced (2026-10-13, website rows 2026-10-14)

Rule: a number may appear on the website, in the README, the case study, the demo scripts or
a resume only if its row here names the dataset, the campaign folder (raw results), the
commit it was measured at and, for anything decided by the perf gate, the gate version.
Results from different gate versions are never pooled or shown as one figure.

## Gate versions

| id | rule | in force | campaigns |
|---|---|---|---|
| G0 | p95 point change; WARN > 10%, BLOCK > 25%; no warmup wave (biased: identical revisions up to 60% apart) | until 2026-10-09 | 2026-10-04-*, 2026-10-06 |
| G1 | G0 + one unmeasured warmup wave per run | 2026-10-09 to 2026-10-11 | 2026-10-09-gate-warmup, -v2 |
| G2 | median of per-run p95, 95% hierarchical bootstrap, PASS/WARN/BLOCK/INCONCLUSIVE | 2026-10-11 to 2026-10-12 | 2026-10-11-gate-ci, 2026-10-12-gate-ci |
| G3 | frozen: geometric-mean TTFT, run as unit, 90% Welch, 10% / 25%, p95 advisory (6e90c99, 26fa8eb) | from 2026-10-12 | 2026-10-12-gate-validation |

## Website (apps/web; all figures are read from bench/results at render time)

| where | claim | source (campaign / file) | commit, conditions | gate | status |
|---|---|---|---|---|---|
| landing hero (PR review, 2026-10-14) | per trial: the PR's line (read from the repair patch), PR vs main, gate verdict, first strategy rejected, repair vs main and **repair vs PR** with 90% intervals, regression test first, judge SKIP shown as not a pass; labeled "recorded run, not live", trial 1/2/3 switch | `2026-10-12-gate-validation/rq5.json` (`perf.head_vs_base`, `candidate_vs_base`, `candidate_vs_head`, `patch`) | 6efebfd, 780 MHz, AC | G3 | replaces the before/after bars, whose repair figure (+3%) was a ratio of medians taken across different trials; every figure is now within one trial's interleaved runs |
| evidence tile: false alarms 0/36 (PASS 29/36) | V1 + V2 unchanged-code sets | `2026-10-12-gate-validation/validation/report.json` (`sets.v1_aa`, `sets.v2_restored`; affected trials excluded as planned) | 780-828 MHz | G3 | new 2026-10-14 |
| evidence tile: R1 blocked 6/6 | V3a | same file, `sets.v3a_r1` | as above | G3 | new 2026-10-14 |
| evidence tile: repairs 3/3 | "repeated trials of one scenario (F1, R1), not a rate over apps or regression types" | `2026-10-12-gate-validation/rq5.json` | 6efebfd | G3 | kept |
| evidence tile: p95 TTFT with prefix caching off | c=16, seqs 32 | `2026-10-06/rq4` | 780 MHz, AC | n/a | kept |
| limits tile: small regressions undecided 15/18 | V3b, V3c topk4, topk8; measured range from the set medians | `validation/report.json` | as above | G3 | new: the negative result is on the landing page |
| limits tiles: call sites 32/48, findings right 39/77 (recall 39/64) | held-out set 6 first scan | pinned `2026-10-13-set6/rq1.json`, `set6/findings.json` | scanner 41ca529, labels ebd5824 | n/a | findings precision added 2026-10-14 |
| limits tile: live GitHub runs 0 | shown until a `bench/results/<date>-live-github/` campaign exists | campaign list | n/a | n/a | new |
| /pilot text: "39 of its 77 findings were right" on five unseen apps | static text (the page is prerendered) | `2026-10-13-set6/set6/findings.json` `pooled` | scanner 41ca529 | n/a | frozen held-out result; findings judged by the developer agent, not independently reviewed |
| landing "How it works": Connect and Review marked "tested against a mock GitHub only" | until the live run is recorded | `docs/completion.md` E | | | update the two markers after `live_run.md` and `verify.md` pass |
| RQ3 tile (3/3 caught, 46%, 13 PRs) | removed from the landing page 2026-10-14 (G0-era; still on /guard with a G0 label) | `2026-10-06/rq3.json` | | G0 | /guard now says the gate was later found biased and that every perf verdict in that table depends on it |
| /lab | RQ4 cells, live run | `2026-10-06/rq4`; live runs are labeled live | 780 MHz | n/a | ok |
| /guard, /guard/<scenario> | RQ3 selections; RQ5 timeline | newest rq3 (G0) and newest rq5 | as recorded | each page names its metric | ok; /guard RQ3 table labeled with its gate (2026-10-14) |
| /evals | deterministic checks on seeded failures; human/judge parts | newest rq2 | as recorded | n/a | ok (judge and labels shown as not run) |
| /bench | every campaign with its corrections | all folders | per folder | per folder | ok |

## README, case study, demo scripts

| claim | source | gate | status |
|---|---|---|---|
| held-out first-scan call sites 4/34 (P 4/4) over sets 1-5 | `2026-10-12-reconcile/scanner_reconciliation.md` | n/a | ok; to be joined (not pooled) by set 6 |
| set 6: call sites 32/48 (32/32 correct); finding precision 39/77, recall 39/64; citations 148/148 | `2026-10-13-set6/` (`rq1.md`, `set6/`, `NOTES.md`) | n/a | in README; reported beside sets 1-5, not pooled |
| R1 size: p95 TTFT +905% to +1,004%, hit 98% -> 0% | `2026-10-09-gate-warmup-v2/rq5.md` | G1 measurement (a p95 effect size, not a verdict) | ok as labeled (p95, that campaign) |
| repair 1/3 verified | `2026-10-12-gate-ci/rq5.md` | G2 | ok as labeled; never pooled with G3 |
| repair 3/3 verified = 3 repeated trials of one scenario (F1, R1); accepted at +4.2% / +0.9% / +1.7% vs main (90% upper bounds 9.5 / 4.1 / 7.2, acceptance needs < 25); -85.5% / -85.6% / -86.0% vs the PR (90% intervals -86.2..-84.9 / -86.0..-85.2 / -86.7..-85.2, acceptance needs the upper bound < 0; column added to rq5.md 2026-10-14 from the stored comparisons, no rerun); first strategy rejected 3/3; prompts byte-identical to main 34/34; judge skipped | `2026-10-12-gate-validation/rq5.md`, `rq5/`, `rq5/prompt_identity.md`, `NOTES.md` | G3 | done |
| optimizer: keep the baseline; confirmation inconclusive (goodput +3.8%, 90% CI -8.8 to +18.2) | `2026-10-12-optimizer/NOTES.md`, `optimizer/{optimizer,confirm}.md` | n/a | done; no improvement claimed |
| RQ3 46% of checks, 3/3 caught, 13/13 same conclusion | `2026-10-06/rq3.md` | G0 | say "under the gate of 2026-10-06 (later found biased)" wherever it appears |
| RQ4 +193% to +433% (seqs 32), all 15 cells | `2026-10-06/rq4` | n/a | ok, 780 MHz |
| A/A: 0 false WARN/BLOCK in 12, max +13.4% | `2026-10-11-gate-ci` | G2 | ok as labeled |
| gate validation: 63 trials = 60 counted + 3 affected; 0/36 false FAIL, PASS 29/36, INCONCLUSIVE 7/36; R1 BLOCK 6/6; graded sets INCONCLUSIVE 15/18 / PASS 3/18; 780-828 MHz | `2026-10-12-gate-validation/validation/{report,trials}.md`, `NOTES.md` | G3 | done |
| Kernel Lab 36/36, parity with torch.compile | `kernel_lab/results/2026-10-09/` | n/a | ok |

## Resume

No resume file found on the Desktop mentions Furnace (checked 2026-10-13 by file name and
the `.tex` source; the PDFs are checked after the GPU run). Any Furnace bullet must quote a
row above, with its denominator and, for gate results, the gate version.
