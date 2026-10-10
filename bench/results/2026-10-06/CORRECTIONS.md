**Corrections and updates, 2026-10-09.** This campaign's report below is generated from its result files and is left as it was.

**1. The perf gate was biased, so RQ5's "3/3 verified" does not hold.** Without a warmup wave, the first requests after the GPU sat idle took ~200 ms instead of ~65 ms and set each run's p95; the base revision, measured first, read ~2.4x slower. An A/A test (main vs itself) showed differences up to 60%; with a warmup wave the A/A noise is at most 9.7% (`2026-10-09/gate_noise.md`). Re-measured, R1 costs **+905% to +1,004%** p95 TTFT (not +336% to +414%), and the repair reported below ("move to the end of the user message") is **+40% to +50%** over main and is blocked: 0/3 (`2026-10-09-gate-warmup/`).

**2. Current result** (`2026-10-09-gate-warmup-v2/`): the repair loop now tries a second strategy, logging the per-request values instead of sending them: **3/3 verified at -2.0% to +8.5% vs main**, prefix-cache hit 98% -> 98%, 3/3 full-suite audits clean.

**3. "Capped GPU clock" was the wrong word.** The laptop GPU reaches 1,850 MHz under a saturating load; under this serving load the driver holds ~780 MHz with no throttle reason active (NOTES.md, 2026-10-09 addendum).

RQ1, RQ2 and RQ4 do not use the perf gate. RQ3's perf-gate noise figures came from the biased gate; its regression recall did not depend on them.

**4. RQ1 update (new results, not a correction).** A new held-out set 3 (Gemini, Mistral, Replicate, Bedrock, Cohere apps; labeled before any scan) measured the SDK-coverage change: LLM call sites **1/9 -> 8/9** at precision 1.00, Streamlit/CLI workflows 0/9 -> 6/9. Set 2, below, is no longer held-out (it was seen while building the change): 1/5 -> 5/5. A scorer bug that never matched call sites inside class methods was fixed and both scanners were re-scored (`2026-10-09/RQ1_NOTES.md`, `2026-10-09/rq1.md`).
