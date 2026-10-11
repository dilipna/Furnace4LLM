# Same live run, two GPU clocks (laptop RTX 3050 Ti, lab vLLM, Qwen2.5-0.5B)

Two "Run it now" runs (`POST /api/live/bench`: c = 1, 2, 4, 8 x 20 requests, F1 workload
fingerprint, prefix caching on), identical code and endpoint configuration. The only difference
observed is the SM clock the driver chose under this load, after a reboot in between.

| run | started (UTC) | SM clock | p95 TTFT c=1 | c=2 | c=4 | c=8 | prefix-cache hit |
|---|---|---:|---:|---:|---:|---:|---:|
| `runs/6e4ec05557ae` | 2026-10-09 02:16 | 780 MHz | 54 ms | 66 ms | 106 ms | 137 ms | 88-89% |
| `runs/bd1286537d74` | 2026-10-11 03:25 | 1,957-1,971 MHz | 31 ms | 45 ms | 55 ms | 91 ms | 89-91% |

p95 TTFT is 32% to 48% lower at the higher clock. Both runs are single runs (no repeats), so this
is an observation, not an effect estimate. It is why every GPU result records its clock and why
comparisons are only made inside a run set that shares one: the FurnaceBench RQ3, RQ4 and RQ5
numbers were all measured at ~780 MHz, and the /lab reference ticks say so.
