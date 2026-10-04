"""WorkloadSpec: the fingerprint of an application's LLM traffic.

Lives in furnace-bench (not furnace) so the benchmark engine stays standalone:
a WorkloadSpec YAML/JSON file is everything needed to generate load.
Python 3.10 compatible on purpose (Kaggle/Colab runtimes).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class WorkloadSource(str, Enum):
    traces = "traces"  # derived from real production/sample traces
    endpoint_probe = "endpoint_probe"  # short measured probe against an endpoint
    static_estimate = "static_estimate"  # estimated from source code (prompts, top_k, max_tokens)
    synthetic = "synthetic"  # hand-specified / generated


class TrafficClass(str, Enum):
    interactive = "interactive"
    batch = "batch"
    long_context = "long_context"
    high_concurrency = "high_concurrency"
    tool_agent = "tool_agent"


class Distribution(BaseModel):
    """Empirical distribution summary of a positive integer quantity (tokens)."""

    n: int = 0
    mean: float = 0.0
    p50: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    min: float = 0.0
    max: float = 0.0
    # Histogram as (bin_upper_edge, count) pairs; used to sample synthetic lengths.
    hist: list[tuple[float, int]] = Field(default_factory=list)


class PrefixGroup(BaseModel):
    prefix_hash: str
    tokens: int
    share: float  # fraction of requests starting with this prefix


class PrefixStats(BaseModel):
    block_size: int = 16
    # Fraction of prompt tokens reusable from earlier requests with an unbounded cache.
    reuse_ratio_infinite: float | None = None
    # Same, simulating an LRU cache of `lru_capacity_tokens` tokens.
    reuse_ratio_lru: float | None = None
    lru_capacity_tokens: int | None = None
    groups: list[PrefixGroup] = Field(default_factory=list)


class ArrivalStats(BaseModel):
    mean_rps: float | None = None
    # Coefficient of variation of inter-arrival times; ~1.0 is Poisson, >1 bursty.
    cv_interarrival: float | None = None
    peak_concurrency: int | None = None
    # (concurrency, fraction_of_time) pairs
    concurrency_hist: list[tuple[int, float]] = Field(default_factory=list)


class SLO(BaseModel):
    ttft_p95_ms: float | None = None
    tpot_p95_ms: float | None = None
    e2e_p95_ms: float | None = None
    max_failure_rate: float = 0.01

    def per_request_ok(
        self, ttft_ms: float | None, tpot_ms: float | None, e2e_ms: float | None
    ) -> bool:
        """Per-request SLO test used by goodput. p95 targets are applied per request:
        a request counts toward goodput only if it individually meets every set bound."""
        if self.ttft_p95_ms is not None and (ttft_ms is None or ttft_ms > self.ttft_p95_ms):
            return False
        if self.tpot_p95_ms is not None and tpot_ms is not None and tpot_ms > self.tpot_p95_ms:
            return False
        if self.e2e_p95_ms is not None and (e2e_ms is None or e2e_ms > self.e2e_p95_ms):
            return False
        return True


class WorkloadSpec(BaseModel):
    schema_version: str = "furnace.workload/v1"
    name: str = "default"
    source: WorkloadSource
    synthetic: bool  # True whenever the numbers are not measured from real traffic
    model: str | None = None
    tokenizer: str | None = None  # e.g. "Qwen/Qwen2.5-0.5B-Instruct" or "o200k_base (approx)"
    n_observed: int = 0
    window_seconds: float | None = None

    input_tokens: Distribution = Field(default_factory=Distribution)
    output_tokens: Distribution = Field(default_factory=Distribution)
    system_prompt_tokens: Distribution | None = None
    rag_context_tokens: Distribution | None = None

    prefix: PrefixStats = Field(default_factory=PrefixStats)
    arrival: ArrivalStats = Field(default_factory=ArrivalStats)
    streaming_ratio: float | None = None
    traffic_class: list[TrafficClass] = Field(default_factory=list)
    slo: SLO = Field(default_factory=SLO)

    # field name -> human-readable provenance ("traces:42 records", "static: src/app.py:88", ...)
    field_provenance: dict[str, str] = Field(default_factory=dict)
