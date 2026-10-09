// Shapes of the FurnaceBench result files served by /api/bench (written by bench/rq*.py).
import { ApiError, apiGet } from "@/lib/api";

export type Agg = { median: number | null; min: number | null; max: number | null; n: number };

export type Campaign = { name: string; available: string[]; has_report: boolean };

export type Rq4Row = {
  config: string;
  level: number;
  repeats: number[];
  ttft_p50_ms: Agg;
  ttft_p95_ms: Agg;
  ttft_p99_ms: Agg;
  tpot_p50_ms: Agg;
  e2e_p95_ms: Agg;
  throughput_rps: Agg;
  output_tok_s: Agg;
  goodput_rps: Agg;
  failure_rate: Agg;
  prefix_hit_rate: Agg;
};

export type Rq4 = {
  manifest: {
    gpu?: string;
    memory_mb?: number;
    driver?: string;
    image_digest?: string;
    model?: string;
    git?: { sha: string | null };
  };
  engine: { engine?: string; engine_version?: string } | null;
  workload: {
    file: string;
    input_tokens_mean: number;
    shared_prefix_tokens: number;
    expected_prefix_hit_rate: number;
    trace_reuse_ratio: number;
  };
  slo_ttft_p95_ms: number;
  rows: Rq4Row[];
  prefix_effect: {
    max_num_seqs: number;
    level: number;
    n_pairs: number;
    ttft_p95_off_vs_on_pct: Agg;
    goodput_on_minus_off_rps: Agg;
    consistent_sign: boolean;
  }[];
  launch_failures: { config: string; repeat: number }[];
  clocks?: { config: string; repeat: number; sm_clock_mhz_mean: number; power_w_max: number; temp_c_max: number; on_ac: boolean | null }[];
  clock_spread_pct?: number | null;
};

export type Workload = {
  source: string;
  spec: {
    name: string;
    n_observed: number;
    input_tokens: { p50: number; p95: number; mean: number };
    output_tokens: { p50: number; p95: number; mean: number };
    system_prompt_tokens?: { p50: number } | null;
    prefix: { reuse_ratio_infinite: number; groups: { tokens: number; share: number }[] };
    arrival: { mean_rps: number; cv_interarrival: number; peak_concurrency: number };
    field_provenance: Record<string, string>;
  };
};

export async function campaigns(): Promise<Campaign[]> {
  return apiGet<Campaign[]>("/api/bench/campaigns");
}

/** Newest campaign that has `rq`, or null. */
export async function latestWith(rq: string): Promise<string | null> {
  const list = await campaigns();
  return list.find((c) => c.available.includes(rq))?.name ?? null;
}

export async function getRq<T>(campaign: string, rq: string): Promise<T | null> {
  try {
    return await apiGet<T>(`/api/bench/campaigns/${campaign}/${rq}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

/** "pc-on_seqs-32" -> { prefixCache: true, seqs: 32 } */
export function parseConfig(c: string): { prefixCache: boolean; seqs: number } {
  const m = /^pc-(on|off)_seqs-(\d+)$/.exec(c);
  return { prefixCache: m?.[1] === "on", seqs: Number(m?.[2] ?? 0) };
}

export type ItemVerdict = "pass" | "fail" | "warn" | "skip" | "error";

export type Rq3Scenario = {
  scenario: string;
  description: string;
  seeded: string | null;
  categories: string[];
  fell_back_to_full: boolean;
  impact_seconds: number;
  selected: string[];
  skipped: { key: string; reason: string }[];
  full: { key: string; verdict: ItemVerdict; seconds: number; detail: string }[];
  full_fail: string[];
  full_warn: string[];
  missed_fail: string[];
  missed_warn: string[];
  full_seconds: number;
  targeted_seconds: number;
  full_endpoint_seconds: number;
  targeted_endpoint_seconds: number;
  targeted_conclusion: string;
  full_conclusion: string;
};

export type Rq3 = {
  summary: {
    scenarios: number;
    suite_items: number;
    items_executed_pct: number;
    wall_seconds: { full: number; targeted: number };
    endpoint_seconds: { full: number; targeted: number };
    regression_recall: { caught: number; total: number; recall: number | null };
    warn_recall: { caught: number; total: number };
    conclusion_agreement: number;
  };
  scenarios: Rq3Scenario[];
};

export type GateCompare = {
  baseline: number;
  value: number;
  change_pct: number;
  verdict: string;
  prefix_hit_rate?: [number | null, number | null] | null;
  runs?: number;
  separated?: boolean;
};

export type RepairAttempt = {
  scenario: string;
  repeat: number;
  status: string;
  repro: { head_fails: boolean; base_passes: boolean; logs: string } | null;
  localization: { node_key: string; file: string; hunk: { new_start: number; new_lines: number } | null; score: number; reasons: string[] }[];
  candidates: { strategy: string; verdict: string | null; regression_test?: string; existing_tests?: string; explanation?: string; perf_summary?: string | null }[];
  perf: { head_vs_base?: GateCompare; candidate_vs_base?: GateCompare; within_budget?: boolean; summary?: string };
  logs: Record<string, string>;
  stages: { t: number; stage: string; msg: string }[];
  repair_seconds: number;
  patch: string;
  audit?: { conclusion: string; items: { key: string; verdict: ItemVerdict; detail: string; seconds: number }[]; new_failures: string[] };
};

export type Rq5 = { attempts: RepairAttempt[] };

export type LiveGuard = {
  scenario: string;
  results: { key: string; verdict: ItemVerdict; detail: string; seconds: number }[];
  check_md: string | null;
};
