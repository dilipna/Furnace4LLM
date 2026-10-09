# RQ5 with the warmed-up gate and two repair strategies (2026-10-09)

- Perf gate: one unmeasured warmup wave before every measured run (A/A noise after the fix:
  max |change| 9.7%, `../2026-10-09/gate_noise.md`). Laptop RTX 3050 Ti on AC, SM clock ~780 MHz
  under this load (driver choice, not throttling: `../2026-10-06/NOTES.md`, 2026-10-09 addendum).
- Strategies tried in order. In all 3 attempts `move_dynamic_to_suffix` (values kept in the prompt)
  was blocked at +44% to +50% p95 TTFT; `move_dynamic_to_log` (values logged instead of sent) passed
  at -2.0% to +8.5%, inside the measured noise, prefix-cache hit 98% -> 98%, full-suite audit clean.
- Trade-off of the proposed fix, stated in the repair PR: the model no longer sees the request id
  and timestamp. For R1 ("for debugging") that is the intent; for a value the model needs, a human
  would choose the suffix candidate, whose measured cost is listed beside it.
- The LLM judge item is SKIPPED (no key configured), as in every campaign.
