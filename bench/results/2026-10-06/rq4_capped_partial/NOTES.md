# RQ4 partial sweep at a platform-capped GPU clock (2026-10-06, discarded)

Five runs (repeat 0 of pc-on_seqs-8/32/128 and pc-off_seqs-8/32) completed on AC power
between 03:28 and ~03:50 UTC while the laptop held the GPU at ~780-815 MHz (P0, ~34 W,
80 W limit, no NVML throttle reason) as the battery recharged from 14% to 36%. The session
then ended before the sweep finished. Because the clock was drifting upward with the
battery level, these runs are not mixed with the fresh sweep in `../rq4/`; they are kept
for the record only.
