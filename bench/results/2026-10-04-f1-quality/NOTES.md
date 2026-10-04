# F1 quality baseline from real traffic (2026-10-04)

**Setup.** F1 (`fixtures/apps/support-rag-py`, unmodified prompt) served by vLLM 0.30.0 on an
RTX 3050 Ti Laptop. `scripts/traffic.py --rate 2 --repeat 2 --seed 7`: 88 questions (68 documented
facts, 12 out-of-scope, 8 needing a human), Poisson arrivals. Traces are the app's own call log.

**Deterministic checks on the traces** (`furnace.evals.runner`):

| model | citation_required PASS | TTFT ≤ 500 ms PASS |
|---|---:|---:|
| Qwen2.5-0.5B-Instruct (fp16) | 3 / 89 | 88 / 89 |
| Qwen2.5-1.5B-Instruct-AWQ | 9 / 88 | 87 / 88 |

(The 0.5B run includes one extra manual smoke request.) Neither model uses the documented
"I could not find that in the Kilnworks documentation." phrasing for out-of-scope questions (0 / 12).

**Failures observed that need a semantic judge (not caught by deterministic checks):**
- 1.5B-AWQ, "What is the price of the Enterprise plan?" -> invents an Enterprise plan at
  "$79 per month ... up to 5 kilns" (no such plan; $79 is the Workshop plan, 12 kilns).
- 1.5B-AWQ, "My kiln smells like burning plastic during firing" -> advises removing the safety
  sensors, which the system prompt explicitly forbids.
- 0.5B, "Can safety interlocks be disabled remotely?" -> "Yes, safety interlocks cannot be disabled..."

**Serving trade-off on the 4 GB GPU:** KV cache 120,848 tokens (0.5B fp16) vs 24,672 tokens
(1.5B AWQ) at `--gpu-memory-utilization 0.70`.

**Workload fingerprint** (0.5B traces, exact Qwen tokenizer): prompt p50 965 / p95 980 tokens,
system prompt 849 tokens, output p50 25 / p95 162, prefix reuse 93.5% (one 857-token group
covering 100% of requests), arrival 2.06 req/s with CV 0.98 (generator: Poisson at 2.0 req/s),
peak concurrency 5. The Blueprint's 4-chars/token estimate of the system prompt (~982 tokens)
was 16% high.
