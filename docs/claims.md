# Claims ledger: every public number, traced (2026-10-13)

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
| landing tile 1 | LLM call sites found on never-seen apps, a/b | pinned `2026-10-13-set6/rq1.json`, split held-out-6 | scanner 41ca529 (frozen), labels ebd5824 | n/a | **fixed 2026-10-13**: it showed set 3 after the scanner was fixed on set 3 (8/9) as "labeled before the scanner saw them"; figure appears once the set-6 RQ1 run is stored |
| landing tile 2 | regressions caught 3/3, 46% of checks, 13 PRs | `2026-10-06/rq3.json` | 2026-10-06 commits (map: `bench/results/commit-map.txt`), 780 MHz | G0 | label now names the campaign and gate |
| landing tile 3 | p95 TTFT with prefix caching off, c=16, seqs 32 | `2026-10-06/rq4` | 780 MHz, AC | n/a (direct benchmark) | label now names campaign and clock |
| landing tile 4 | prompt-cache repairs verified x/3 | newest campaign with rq5 | as recorded in that rq5.json | named from the stored metric (G3 if geometric mean) | label now names campaign and gate; becomes the G3 result when V4 is stored |
| landing hero | R1 before/after, first candidate blocked | newest campaign with rq5 (single campaign) | as recorded | one gate (that campaign's) | consistent; switches to G3 with V4 |
| /lab | RQ4 cells, live run | `2026-10-06/rq4`; live runs are labeled live | 780 MHz | n/a | ok |
| /guard, /guard/<scenario> | RQ3 selections; RQ5 timeline | newest rq3 (G0) and newest rq5 | as recorded | each page names its metric | ok; pending: gate label on /guard RQ3 table |
| /evals | deterministic checks on seeded failures; human/judge parts | newest rq2 | as recorded | n/a | ok (judge and labels shown as not run) |
| /bench | every campaign with its corrections | all folders | per folder | per folder | ok |

## README, case study, demo scripts

| claim | source | gate | status |
|---|---|---|---|
| held-out first-scan call sites 4/34 (P 4/4) over sets 1-5 | `2026-10-12-reconcile/scanner_reconciliation.md` | n/a | ok; to be joined (not pooled) by set 6 |
| set 6: finding precision 39/77, recall 39/64; citations 148/148 | `2026-10-13-set6/set6/{findings,citations}.md` | n/a | new; not yet in README |
| R1 size: p95 TTFT +905% to +1,004%, hit 98% -> 0% | `2026-10-09-gate-warmup-v2/rq5.md` | G1 measurement (a p95 effect size, not a verdict) | ok as labeled (p95, that campaign) |
| repair 1/3 verified | `2026-10-12-gate-ci/rq5.md` | G2 | ok as labeled; G3 result pending (V4) |
| RQ3 46% of checks, 3/3 caught, 13/13 same conclusion | `2026-10-06/rq3.md` | G0 | needs "under the gate of 2026-10-06" next to it |
| RQ4 +193% to +433% (seqs 32), all 15 cells | `2026-10-06/rq4` | n/a | ok, 780 MHz |
| A/A: 0 false WARN/BLOCK in 12, max +13.4% | `2026-10-11-gate-ci` | G2 | ok as labeled |
| gate validation figures | `2026-10-12-gate-validation/validation/report.md` | G3 | pending the run; README/case study say "in progress" until then |
| Kernel Lab 36/36, parity with torch.compile | `kernel_lab/results/2026-10-09/` | n/a | ok |

## Resume

No resume file found on the Desktop mentions Furnace (checked 2026-10-13 by file name and
the `.tex` source; the PDFs are checked after the GPU run). Any Furnace bullet must quote a
row above, with its denominator and, for gate results, the gate version.
