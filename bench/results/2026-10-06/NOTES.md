# Campaign notes, 2026-10-06 (directory pinned with FURNACE_BENCH_DATE=2026-10-06)

- **Power.** The first RQ4 sweep ran on battery and was discarded (`rq4_battery_invalid/NOTES.md`).
  A second sweep on AC was cut short by a session end and discarded (`rq4_capped_partial/NOTES.md`).
- **GPU clock cap.** On AC, before and after a reboot, at 14% and at 56% battery, the laptop held
  the RTX 3050 Ti at **~780-830 MHz mean SM clock** under load (spot samples: P0, ~30-34 W, 80 W
  enforced power limit, no NVML throttle reason active; RQ4 telemetry recorded power peaks up to 64 W). The GPU's maximum is 2,100 MHz; the 2026-10-04 runs
  averaged 1,948 MHz and 72 W. This is a platform policy (OEM performance mode, Windows power
  mode or charger wattage), not something Furnace controls; it was not changed for this campaign.
- **Consequence.** The final RQ3, RQ4 and RQ5 results in this directory ran at that capped clock.
  Comparisons inside each RQ (configs, base vs PR vs repair) share the clock and are valid;
  absolute latencies are not comparable to the 2026-10-04 results. Each RQ4 run records its SM
  clock and AC state (`rq4/rq4.json` -> `clocks`, `clock_spread_pct`).
- **Host.** Development continued on the same machine during the GPU runs: editor, a Next.js dev
  server, the FastAPI dev server, the test suite (`poe check`, including short Docker sandbox tests)
  and Playwright screenshots. This adds CPU noise to client-side timing; repeats and revisions are
  interleaved so it spreads across configs rather than biasing one.
