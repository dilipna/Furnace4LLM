# FurnaceBench

FurnaceBench is how Furnace measures its own claims. Each research question (RQ) has one
driver in `bench/`, one `poe` command, and writes JSON plus Markdown into
`bench/results/<date>/` (UTC date; `FURNACE_BENCH_DATE=YYYY-MM-DD` pins a directory so
several sessions can add to one campaign). `bench-report` assembles `REPORT.md` from
those files only: if a number is not in a results file, it is not in the report.

## Commands

```bash
uv run poe bench-setup     # clone held-out apps at pinned commits; check vLLM image + cached models
uv run poe bench-rq1       # reconstruction vs ground truth          -> rq1.{json,md}
uv run poe bench-rq2       # evaluator quality (seeded; human labels)  -> rq2.{json,md}
uv run poe bench-rq3       # impact-aware selection vs full suite (GPU) -> rq3.{json,md}, rq3/
uv run poe bench-rq4       # vLLM sweep, 3 repeats (GPU, ~1 h)          -> rq4/rq4.{json,md}, rq4/runs/
uv run poe bench-rq5       # failing-test-first repair x3 (GPU)         -> rq5.{json,md}, rq5/
uv run poe bench-report    # -> REPORT.md
uv run python bench/gate_noise.py          # perf-gate A/A characterization (GPU) -> gate_noise.{json,md}
uv run python bench/gate_dev_analysis.py   # gate revision: statistic/interval choice on stored A/A data (CPU)
uv run python bench/gate_validate.py run --set v1_aa   # fresh gate validation, one set (GPU; sets in the file)
uv run python bench/gate_validation_report.py          # validation report: frozen vs replaced rule, targets
uv run python bench/optimize.py           # quality-constrained config optimizer, 8-config grid (GPU, ~45 min)
uv run python bench/correlation.py        # TTFT vs vLLM queue state on the stored RQ4 runs (CPU)
uv run python bench/scanner_reconcile.py  # scanner metrics with counts and denominators (CPU)
uv run python bench/rq1.py --splits held-out-3 --tag set3_baseline   # one split, own output name
uv run python bench/label.py   # label the RQ2 human queue (60 items, resumable)
```

Prerequisites: Docker Desktop with the NVIDIA runtime, `docker compose up -d postgres`,
and the lab endpoint `HF_HOME_HOST=... docker compose --profile gpu up -d vllm` (port
8100) for RQ3/RQ5. RQ4 stops that container, launches its own (port 8101) per config,
and restarts it at the end. Never run two GPU drivers at once: they share one GPU and
would contaminate each other's latency.

## Research questions and protocols

| RQ | Question | Ground truth | Main metrics |
|---|---|---|---|
| RQ1 | Does Scan reconstruct an app correctly? | `fixtures/apps/support-rag-py/ground_truth.yaml` (dev fixture) and `bench/ground_truth/*.yaml` (held-out OSS apps, labeled from source before their first scan, at pinned commits) | P/R/F1 per category, attribute accuracy next to an empty-scan baseline, confidence ECE |
| RQ2 | Do the evaluators detect what they claim? | (1) mutation operators with known effect on each check's spec; (2) human labels on 60 real answers; (3) LLM judge on held-out labels | recall, precision, FPR per check; check-vs-human agreement; judge TPR/TNR |
| RQ3 | Does graph-based selection keep regression recall while running less? | FAIL verdicts of the full suite per PR scenario (13 scenarios on F1) | % of suite executed, wall time, endpoint time, regression recall with misses listed |
| RQ4 | How does F1's real workload behave on the lab GPU? | measurement (3 repeats, fresh server per repeat, interleaved, paired seeds) | TTFT/TPOT/E2E percentiles with bootstrap CIs, goodput at the SLO, prefix-cache hit rate vs prediction |
| RQ5 | Does failing-test-first repair work repeatably? | regression test must fail on head and pass on base; full-suite audit of the repaired tree | verified repairs / attempts, perf vs base, audit result |

### Rules

- **Held-out means held-out.** Ground truth for a held-out app is committed before Furnace
  is run on it. Results from that first scan are frozen (`rq1_first_scan.*`). If the
  scanner is changed because of those errors, later RQ1 runs on the same apps are
  reported as "after fixes, no longer held-out".
- **Repeats and spread.** Inference and repair runs use 3 repeats and report
  median [min, max], plus paired per-repeat differences where the design allows.
- **Negative results are results.** Every driver writes its failures (launch failures,
  missed regressions, rejected repairs, SKIP items) into its Markdown, and `REPORT.md`
  collects them in one section.
- **Measure the instrument.** The perf gate is characterized with A/A runs (a revision
  against itself) and validated on fresh trials before it is trusted; a gate revision is
  designed on old data and frozen before it is validated (`docs/gate-revision.md`).
- **Corrections are dated, never edits.** A generated report is not rewritten after the fact;
  a `CORRECTIONS.md` next to it says what no longer holds and where the new result is, and the
  `/bench` page shows it above the report.
- **Labels are named.** Every number states its ground-truth source; seeded results are
  never presented as agreement with human judgment.

## The perf gate's decision rule (since 2026-10-12)

Full design, the data behind it and the validation protocol: `docs/gate-revision.md` (frozen
before the code changed).

What is measured: for each revision, prompts rendered by that revision's own code in the
sandbox, each request carrying a unique reference (never a verbatim repeat), replayed by
`furnace-bench` at concurrency 8 against the lab vLLM after one unmeasured warmup wave.
Revisions share the GPU, so they run one after another; repeats are interleaved and their
order rotates every repeat (a Latin square), because the A/A study found the side measured
first biased.

Statistic: each run is reduced to one number, the mean of log TTFT over its successful
requests (its geometric-mean TTFT). Requests are never resampled: in a closed loop they
arrive in waves that share a scheduler step, so they are not independent; the run is the
unit. The change is the ratio of the two sides' geometric means; its uncertainty is a
two-sided **90% Welch t interval** across runs (at least 3 per side), so each tail is a
one-sided 95% bound. The p95 is computed the same way and reported as advisory only.

| verdict | rule (90% interval [lo, hi] of the change, tolerance T = 10%, block B = 25%) | check run |
|---|---|---|
| PASS | hi ≤ T: a regression beyond the tolerance is ruled out | success |
| BLOCK | lo > T and change > B | failure |
| WARN | lo > T and change ≤ B: a real but modest regression | neutral |
| INCONCLUSIVE | lo ≤ T < hi, or fewer than 3 runs a side | neutral, never success |
| (failures) | more failed requests than the base by over 1 point: BLOCK regardless of latency | failure |

Repair candidates are gated separately from their functional tests: accepted only if the
interval against the PR head lies below zero and the interval's upper bound against the base
is below B. Whether it is within T of the base is reported, not assumed.

What the rule gives up: a regression confined to the slowest few percent of requests, with
the typical request unchanged, does not move the geometric mean and is not decided on (it
shows in the advisory p95).

History: from 2026-10-11 to 2026-10-12 the gate used the median across runs of each run's
p95 with a 95% hierarchical bootstrap (runs, then requests); it returned INCONCLUSIVE for
unchanged code in 5/12 (3 runs a side) and 7/8 (5 runs) trials, and its request-level
resampling treated dependent requests as independent. Results produced under it say so in
their `method` field.

## Not yet covered (see REPORT.md "Not run")

LLM judge (needs a Groq/OpenRouter key), human labels (queue ready), TypeScript apps
(no TS extractor), Kaggle T4 runs (fp16 vs AWQ), Ollama comparison, the LLM-patch repair
strategy, and serving-config regressions (RQ3 does not deploy a server per revision).
