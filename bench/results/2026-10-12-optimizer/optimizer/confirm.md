# Optimizer: independent confirmation against the baseline

Baseline `q05_pc-on_seqs-32` (A) vs `q05_pc-on_seqs-8` (B): the selected config (highest median goodput among feasible configs). Fresh container per launch, order ABBAABBA, one performance run per launch (W1, c=8, 120 requests, seed 5000 + launch index), quality once per side on seeds [10, 11, 12] (the grid used [0, 1, 2]). Rules: docs/optimizer.md, fixed before the grid was measured.

**Outcome: inconclusive.**

- SLO goodput, B vs A: +3.8% (90% interval -8.8 to +18.2)
- p95 TTFT, B vs A: +1.0% (90% interval -6.7 to +9.5)
- facts: +0.0 pts (interval -4.0 to +4.0, 21 questions)
- citations: +0.0 pts (interval +0.0 to +0.0, 34 questions)

| launch | side | config | goodput req/s | p95 TTFT ms | failures | SM MHz |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | A | q05_pc-on_seqs-32 | 8.25 | 170 | 0.0% | 780 |
| 2 | B | q05_pc-on_seqs-8 | 7.02 | 166 | 0.0% | 780 |
| 3 | B | q05_pc-on_seqs-8 | 8.34 | 173 | 0.0% | 780 |
| 4 | A | q05_pc-on_seqs-32 | 7.86 | 169 | 0.0% | 780 |
| 5 | A | q05_pc-on_seqs-32 | 7.50 | 148 | 0.0% | 780 |
| 6 | B | q05_pc-on_seqs-8 | 9.10 | 158 | 0.0% | 780 |
| 7 | B | q05_pc-on_seqs-8 | 8.67 | 155 | 0.0% | 780 |
| 8 | A | q05_pc-on_seqs-32 | 8.19 | 159 | 0.0% | 780 |
