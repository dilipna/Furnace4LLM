# RQ4 runs discarded: laptop on battery (2026-10-06)

The first RQ4 sweep (started 02:31 UTC) was stopped after 4 of 18 runs
(`pc-on_seqs-8`, `pc-on_seqs-32`, `pc-on_seqs-128`, `pc-off_seqs-8`, repeat 0, plus a
partial `pc-off_seqs-32`) when throughput at concurrency 1 dropped 4x between two
configs that should not differ at c=1.

Diagnosis (02:56 UTC): Windows reported the battery discharging at 29%. `nvidia-smi`
showed an enforced power limit of **25 W**, SM clock 1,117 MHz (max 2,100), active
clock-event reasons 0x24 (software power cap and software thermal slowdown). The
furnace-bench telemetry in every completed run shows mean SM clock ~780 MHz and
~26 W, versus 1,948 MHz and 72 W in the AC-powered R1 de-risk run of 2026-10-04.

These runs are kept for the record but are **not** RQ4 results: GPU clocks were
capped by the battery power policy, and it is unknown when within the sweep the
power state changed. Since then every GPU driver checks the power state before it
starts (`bench/common.py::require_ac_power`) and records the AC state and enforced
GPU power limit in its manifest.
