# Inference Lab optimizer (quality-constrained config selection)

Workload W1 (F1 trace fingerprint), closed loop at concurrency 8, 120 requests x 3 runs per config; quality on F1's 34 documented questions x 3 seeds with the app's own prompts. Constraints: quality not worse than the baseline by more than 5 points (paired by question, 90% two-sided interval lower bound), failures <= 1%, p95 TTFT <= 500 ms. Cost: N/A (self-hosted, no $/GPU-hour set), so the objective is SLO goodput.

| config | goodput req/s, median (range) | p95 TTFT ms | failures | quality (diff vs baseline, interval, pts) | Pareto | feasible | why not |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| q05_pc-on_seqs-8 | 8.34 (7.37-8.34) | 171 | 0.0% | facts 73.0% (-1.6, -4.3 to +1.2); citations 0.0% (+0.0, +0.0 to +0.0) | yes | yes | – |
| q05_pc-on_seqs-32 (baseline) | 8.30 (7.36-8.37) | 173 | 0.0% | facts 74.6%; citations 0.0% | yes | yes | – |
| q05_pc-off_seqs-8 | 4.69 (4.17-4.70) | 405 | 0.0% | facts 73.0% (-1.6, -7.8 to +4.7); citations 0.0% (+0.0, +0.0 to +0.0) | no | no | facts: -1.6 pts vs baseline (interval -7.8 to +4.7); not shown within the 5-point tolerance |
| q05_pc-off_seqs-32 | 4.36 (4.21-4.45) | 410 | 0.0% | facts 76.2% (+1.6, -1.2 to +4.3); citations 0.0% (+0.0, +0.0 to +0.0) | yes | yes | – |
| q15awq_pc-on_seqs-8 | 6.39 (5.88-6.66) | 431 | 0.0% | facts 85.7% (+11.1, -0.3 to +22.6); citations 12.7% (+12.7, +3.2 to +22.3) | no | yes | – |
| q15awq_pc-on_seqs-32 | 6.39 (5.81-6.61) | 426 | 0.0% | facts 85.7% (+11.1, -0.3 to +22.6); citations 12.7% (+12.7, +3.2 to +22.3) | yes | yes | – |
| q15awq_pc-off_seqs-8 | 3.33 (2.69-3.40) | 1114 | 0.0% | facts 85.7% (+11.1, -0.3 to +22.6); citations 12.7% (+12.7, +3.2 to +22.3) | no | no | p95 TTFT 1114 ms > SLO 500 ms |
| q15awq_pc-off_seqs-32 | 3.01 (2.49-3.33) | 1096 | 0.0% | facts 85.7% (+11.1, -0.3 to +22.6); citations 12.7% (+12.7, +3.2 to +22.3) | no | no | p95 TTFT 1096 ms > SLO 500 ms |

**Pick:** q05_pc-on_seqs-8. **Recommendation:** keep q05_pc-on_seqs-32: q05_pc-on_seqs-8 has the highest median goodput, but its run range overlaps the baseline's, so the data do not justify a change.
Indistinguishable on goodput: q05_pc-on_seqs-32.

Limits: one GPU (RTX 3050 Ti laptop, clock recorded per run), one workload, one concurrency; quality is two deterministic checks (numbers in documented answers, citation validity), not a judged answer quality; the three performance runs per config are consecutive on one container, not interleaved across configs.
