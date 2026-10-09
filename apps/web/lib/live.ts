"use client";

import { useEffect, useState } from "react";

/** One sample from GET /api/live/telemetry (vLLM /metrics + NVML on the API host). */
export type LiveSample = {
  ts: number;
  online: boolean;
  error: string | null;
  lab: {
    running: number | null;
    waiting: number | null;
    kv_cache_usage: number | null;
    prefix_hit_rate: number | null;
    prefix_hit_rate_total: number | null;
    gen_tok_s: number | null;
    window_s: number | null;
  } | null;
  gpu: {
    name: string | null;
    sm_clock_mhz: number | null;
    power_w: number | null;
    temp_c: number | null;
    util_pct: number | null;
    mem_used_mb: number | null;
  } | null;
};

/** GET /api/live/recorded: telemetry from one RQ4 run, per second. */
export type Recorded = {
  source: string;
  campaign: string;
  config: string;
  repeat: number;
  run_id: string;
  started_at: string;
  gpu: string | null;
  engine: string;
  series: {
    t: number;
    running: number;
    waiting: number;
    kv_cache_usage: number | null;
    prefix_hit_rate: number | null;
    gen_tok_s: number;
    sm_clock_mhz: number | null;
    power_w: number | null;
    temp_c: number | null;
  }[];
  levels: {
    level: number;
    t0: number | null;
    t1: number | null;
    ttft_p95_ms: number | null;
    prefix_hit_rate: number | null;
    sm_clock_mhz: number | null;
  }[];
  notes: string[];
};

/** A flat row both live samples and recorded seconds map to, so one panel draws either. */
export type Row = {
  t: number; // seconds (epoch for live, run-relative for recorded)
  running: number | null;
  waiting: number | null;
  kv: number | null;
  hit: number | null;
  tok_s: number | null;
  clock: number | null;
  power: number | null;
  temp: number | null;
};

export const fromSample = (s: LiveSample): Row => ({
  t: s.ts,
  running: s.lab?.running ?? null,
  waiting: s.lab?.waiting ?? null,
  kv: s.lab?.kv_cache_usage ?? null,
  hit: s.lab?.prefix_hit_rate ?? null,
  tok_s: s.lab?.gen_tok_s ?? null,
  clock: s.gpu?.sm_clock_mhz ?? null,
  power: s.gpu?.power_w ?? null,
  temp: s.gpu?.temp_c ?? null,
});

export const fromRecorded = (r: Recorded["series"][number]): Row => ({
  t: r.t,
  running: r.running,
  waiting: r.waiting,
  kv: r.kv_cache_usage,
  hit: r.prefix_hit_rate,
  tok_s: r.gen_tok_s,
  clock: r.sm_clock_mhz,
  power: r.power_w,
  temp: r.temp_c,
});

export type LiveState = "connecting" | "online" | "offline" | "disabled" | "unreachable";

const WINDOW = 90; // samples kept (~1 per second)

/** Subscribes to the telemetry stream; keeps the last WINDOW samples. */
export function useTelemetry(): { state: LiveState; samples: LiveSample[] } {
  const [samples, setSamples] = useState<LiveSample[]>([]);
  const [state, setState] = useState<LiveState>("connecting");

  useEffect(() => {
    const es = new EventSource("/api/live/telemetry");
    es.addEventListener("sample", (ev) => {
      const s = JSON.parse((ev as MessageEvent).data) as LiveSample;
      setState(s.online ? "online" : "offline");
      setSamples((prev) => {
        // a reconnect after the lab went down starts a fresh window: never join across a gap
        const keep = s.online && prev.length && !prev[prev.length - 1].online ? [] : prev;
        return [...keep, s].slice(-WINDOW);
      });
    });
    es.addEventListener("disabled", () => {
      setState("disabled");
      es.close();
    });
    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) setState("unreachable");
    };
    return () => es.close();
  }, []);

  return { state, samples };
}

/** Loads the recorded fallback once it is needed. */
export function useRecorded(enabled: boolean): Recorded | null | undefined {
  const [rec, setRec] = useState<Recorded | null | undefined>(undefined);
  useEffect(() => {
    if (!enabled || rec !== undefined) return;
    let live = true;
    fetch("/api/live/recorded")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => live && setRec(d))
      .catch(() => live && setRec(null));
    return () => {
      live = false;
    };
  }, [enabled, rec]);
  return rec;
}

export const fmt = {
  int: (v: number | null) => (v == null ? "–" : Math.round(v).toLocaleString()),
  pct: (v: number | null, d = 0) => (v == null ? "–" : `${(v * 100).toFixed(d)}%`),
  one: (v: number | null) => (v == null ? "–" : v.toFixed(1)),
};
