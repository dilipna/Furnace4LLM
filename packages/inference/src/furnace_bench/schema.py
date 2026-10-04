"""Benchmark plan / result schema (furnace.bench/v1). Python 3.10 compatible."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from furnace_bench.workload_spec import SLO

SCHEMA_VERSION = "furnace.bench/v1"


class AdapterName(str, Enum):
    openai_compat = "openai_compat"
    vllm = "vllm"
    sglang = "sglang"
    ollama = "ollama"


class BenchTarget(BaseModel):
    adapter: AdapterName = AdapterName.openai_compat
    base_url: str  # e.g. http://localhost:8000/v1
    model: str
    api_key_env: str | None = None  # name of env var holding the key; never the key itself
    metrics_url: str | None = None  # Prometheus endpoint, e.g. http://localhost:8000/metrics
    # Free-form description of server launch configuration (flags), recorded for reproducibility.
    server_flags: dict[str, object] = Field(default_factory=dict)
    label: str | None = None  # human label for comparisons, e.g. "vllm prefix-cache=on"


class ArrivalMode(str, Enum):
    closed_loop = "closed_loop"  # N concurrent workers, next request on completion
    poisson = "poisson"  # open loop, exponential inter-arrivals at `rate_rps`
    gamma = "gamma"  # open loop, gamma inter-arrivals (burstiness via shape)


class LengthMode(str, Enum):
    fixed = "fixed"  # sampled max_tokens + ignore_eos where supported
    natural = "natural"  # model decides when to stop


class PromptMode(str, Enum):
    synthetic = "synthetic"  # token-exact generated prompts honoring prefix groups
    replay = "replay"  # replay payloads from a JSONL file


class BenchPlan(BaseModel):
    # Closed loop: number of concurrent workers. Open loop: offered rate in requests/s.
    concurrency_levels: list[float] = Field(default_factory=lambda: [1, 2, 4, 8, 16])
    requests_per_level: int = 200
    warmup_requests: int = 8
    cooldown_s: float = 2.0  # idle time between levels so queues drain
    arrival: ArrivalMode = ArrivalMode.closed_loop
    gamma_shape: float | None = None  # open-loop gamma only; <1 is burstier than Poisson
    length_mode: LengthMode = LengthMode.fixed
    prompt_mode: PromptMode = PromptMode.synthetic
    replay_path: str | None = None
    stream: bool = True
    seed: int = 1234
    ttft_timeout_s: float = 60.0
    total_timeout_s: float = 300.0
    repeats: int = 1
    slo: SLO = Field(default_factory=SLO)
    telemetry_interval_s: float = 0.25


ErrorClass = Literal[
    "connect",
    "http_4xx",
    "http_5xx",
    "ttft_timeout",
    "total_timeout",
    "stream_parse",
    "empty_output",
    "other",
]

TokenCountSource = Literal["server_usage", "local_tokenizer", "chunk_count"]


class RequestRecord(BaseModel):
    """One request's raw timings. All times are milliseconds relative to request send."""

    idx: int
    level: float
    repeat: int = 0
    ok: bool
    error: ErrorClass | None = None
    error_detail: str | None = None
    send_ts: float  # seconds since run start (monotonic)
    headers_ms: float | None = None
    first_byte_ms: float | None = None
    ttft_ms: float | None = None  # first non-empty content delta
    e2e_ms: float | None = None
    tpot_ms: float | None = None
    chunk_gaps_ms: list[float] = Field(default_factory=list)
    n_chunks: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    token_count_source: TokenCountSource | None = None
    prefix_group: str | None = None
    slo_ok: bool | None = None


class Percentiles(BaseModel):
    p50: float | None = None
    p90: float | None = None
    p95: float | None = None
    p99: float | None = None
    mean: float | None = None
    # 95% bootstrap confidence intervals for p50 / p95 / p99
    p50_ci: tuple[float, float] | None = None
    p95_ci: tuple[float, float] | None = None
    p99_ci: tuple[float, float] | None = None


class LevelSummary(BaseModel):
    level: float  # concurrency (closed loop) or offered rate in req/s (open loop)
    repeat: int = 0
    n: int
    n_ok: int
    window_s: float
    ttft_ms: Percentiles
    tpot_ms: Percentiles
    e2e_ms: Percentiles
    inter_chunk_ms: Percentiles
    tokens_per_chunk: float | None = None
    request_throughput_rps: float
    input_tok_s: float | None = None
    output_tok_s: float | None = None
    total_tok_s: float | None = None
    failure_rate: float
    timeout_rate: float
    errors: dict[str, int] = Field(default_factory=dict)
    slo_goodput_rps: float | None = None
    goodput_ratio: float | None = None
    # Server/GPU telemetry aggregates; keys absent when the metric is not exposed.
    telemetry: dict[str, float] = Field(default_factory=dict)
    not_exposed: list[str] = Field(default_factory=list)


class EnvManifest(BaseModel):
    furnace_bench_version: str
    furnace_git_sha: str | None = None
    python: str
    platform: str
    gpu: str | None = None
    gpu_driver: str | None = None
    engine: str | None = None
    engine_version: str | None = None
    image_digest: str | None = None
    model_revision: str | None = None
    started_at: str
    hostname_hash: str | None = None


class BenchReport(BaseModel):
    schema_version: str = SCHEMA_VERSION
    run_id: str
    target: BenchTarget
    plan: BenchPlan
    workload_name: str
    workload_synthetic: bool
    env: EnvManifest
    levels: list[LevelSummary]
    notes: list[str] = Field(default_factory=list)
