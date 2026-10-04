// Shapes returned by the Furnace API scan endpoints (mirrors furnace.contracts).

export type Observation = "direct_observation" | "inference";
export type ClaimStatus = "supported" | "contested" | "unverified";

export interface Claim<T> {
  value: T;
  confidence: number;
  observation: Observation;
  method: string;
  evidence_ids: string[];
  contradicted_by: string[];
  status: ClaimStatus;
  alternatives: { value: unknown; confidence: number; sources: string[]; evidence: string[] }[];
}

export interface Locator {
  path?: string;
  line_start?: number;
  line_end?: number;
  symbol?: string;
  url?: string;
}

export interface Evidence {
  locator: Locator & { fact?: string; kind?: string; key?: string };
  excerpt: string;
  extractor: string;
  observation: Observation;
}

export interface Recommendation {
  id: string;
  rule_id: string;
  area: "application" | "reliability" | "security" | "observability" | "inference";
  title: string;
  why: string;
  priority: "P0" | "P1" | "P2";
  confidence: number;
  verification_method: string;
  evidence_ids: string[];
  node_keys: string[];
  forge_action: string | null;
}

export interface AppSpec {
  purpose: Claim<string> | null;
  architecture: { languages: Record<string, number>; frameworks: Claim<string>[]; services: string[] };
  workflows: { key: string; name: string; steps: string[]; capability_keys: string[]; confidence: number }[];
  routes: { key: string; method: string; path: string; locator: Locator }[];
  llm_calls: {
    key: string;
    locator: Locator;
    api: string;
    provider: Claim<string> | null;
    model: Claim<string> | null;
    streaming: Claim<boolean> | null;
    has_timeout: boolean;
    structured_output: boolean;
    tools_passed: boolean;
  }[];
  endpoints: { key: string; base_url_ref: string | null; engine: Claim<string>; serving_flags: Record<string, unknown> }[];
  prompts: { key: string; locator: Locator; static_chars: number; static_tokens: number | null; dynamic_head: boolean }[];
  rag: { present: Claim<boolean>; retrievers: { key: string; locator: Locator; store: Claim<string>; top_k: Claim<number> | null }[] } | null;
  tools: { key: string; name: string; locator: Locator; side_effect: Claim<string>; approval_gate: Claim<boolean> }[];
  reliability_existing: Record<"evals" | "tests" | "tracing" | "retries" | "timeouts" | "fallbacks" | "rate_limits" | "guardrails", Claim<string>[]>;
  contradictions: {
    subject_key: string;
    predicate: string;
    values: { value: unknown; confidence: number; sources: string[]; rationale: string; evidence: string[] }[];
    note: string;
  }[];
}

export interface ScanInfo {
  id: string;
  status: "queued" | "running" | "succeeded" | "failed";
  project: string;
  repo: string | null;
  commit_sha: string | null;
  stats: Record<string, unknown>;
  error: string | null;
  created_at: string;
  finished_at: string | null;
}

export interface Blueprint {
  scan: ScanInfo;
  appspec: AppSpec;
  recommendations: Recommendation[];
  evidence: Record<string, Evidence>;
}
