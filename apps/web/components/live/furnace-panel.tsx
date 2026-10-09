"use client";

import { useMemo, useState } from "react";
import { fmt, fromRecorded, fromSample, type Row, useRecorded, useTelemetry } from "@/lib/live";

/* GPU power bands for the heat strip (W). Fixed, so a colour always means the same draw. */
const HEAT_BANDS = [12, 18, 24, 30, 40];
const heatColor = (w: number | null) => {
  if (w == null) return "transparent";
  const i = HEAT_BANDS.findIndex((b) => w < b);
  return i === 0 ? "var(--bg-3)" : `var(--heat-${i === -1 ? 5 : i})`;
};

type Metric = {
  key: keyof Omit<Row, "t">;
  label: string;
  unit?: string;
  format: (v: number | null) => string;
};

const METRICS: Metric[] = [
  { key: "running", label: "requests running", format: fmt.int },
  { key: "waiting", label: "requests waiting", format: fmt.int },
  { key: "kv", label: "KV-cache use", format: (v) => fmt.pct(v, 1) },
  { key: "hit", label: "prefix-cache hit", format: (v) => fmt.pct(v, 1) },
  { key: "tok_s", label: "output tokens/s", format: fmt.int },
  { key: "clock", label: "GPU SM clock", unit: "MHz", format: fmt.int },
  { key: "temp", label: "GPU temp", unit: "°C", format: fmt.int },
];

/** Single-series sparkline: 2px neutral line, gaps where the metric was not reported. */
function Spark({ rows, k, cursor }: { rows: Row[]; k: Metric["key"]; cursor: number | null }) {
  const W = 120;
  const H = 28;
  const vals = rows.map((r) => r[k]);
  const nums = vals.filter((v): v is number => v != null);
  if (nums.length < 2) return <div className="h-7" aria-hidden="true" />;
  const lo = Math.min(0, ...nums);
  const hi = Math.max(...nums) || 1;
  const x = (i: number) => (rows.length === 1 ? W : (i / (rows.length - 1)) * W);
  const y = (v: number) => H - 3 - ((v - lo) / (hi - lo || 1)) * (H - 6);
  let d = "";
  vals.forEach((v, i) => {
    if (v == null) return;
    d += `${i > 0 && vals[i - 1] != null ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
  });
  const ci = cursor ?? vals.length - 1;
  const cv = vals[ci];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="h-7 w-full overflow-visible" aria-hidden="true">
      <path d={d} fill="none" stroke="var(--fg-2)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
      {cv != null && (
        <line x1={x(ci)} x2={x(ci)} y1={0} y2={H} stroke="var(--line-strong)" strokeWidth={1} vectorEffect="non-scaling-stroke" />
      )}
    </svg>
  );
}

function Pill({ tone, children }: { tone: "live" | "off"; children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-[3px] border border-line px-1.5 py-0.5 text-[11px] text-fg-1">
      <span
        className={`h-1.5 w-1.5 rounded-full ${tone === "live" ? "bg-ok motion-safe:animate-pulse" : "bg-fg-3"}`}
        aria-hidden="true"
      />
      {children}
    </span>
  );
}

/**
 * The lab endpoint as an instrument: GPU power as a heat strip, and vLLM's own counters
 * as sparklines. Live from /api/live/telemetry; when the endpoint is down, the last
 * recorded RQ4 run, labelled with its source file. Never interpolated, never invented.
 */
export function FurnacePanel({ compact = false }: { compact?: boolean }) {
  const { state, samples } = useTelemetry();
  const live = state === "online";
  const recorded = useRecorded(!live && state !== "connecting");
  const [cursor, setCursor] = useState<number | null>(null);

  const rows: Row[] = useMemo(() => {
    if (live) return samples.filter((s) => s.online).map(fromSample);
    return recorded ? recorded.series.map(fromRecorded) : [];
  }, [live, samples, recorded]);
  const gpuOnly = !live && samples.length > 0 && samples[samples.length - 1].gpu != null;
  const lastGpu = samples[samples.length - 1]?.gpu;

  // Live: the newest second. Recorded: the run's busiest second (labelled with its time),
  // not the idle tail after the last request.
  const busiest = useMemo(
    () => rows.reduce((best, r, i) => ((r.running ?? 0) > (rows[best]?.running ?? 0) ? i : best), 0),
    [rows],
  );
  const at = cursor != null && cursor < rows.length ? cursor : live ? rows.length - 1 : busiest;
  const row = rows[at];
  const t0 = rows[0]?.t ?? 0;
  const tLabel = (i: number) =>
    live
      ? `${Math.round(rows[i].t - rows[rows.length - 1].t)} s`
      : `t = ${Math.round(rows[i].t - t0)} s${cursor == null ? " (busiest second)" : ""}`;

  function onKey(e: React.KeyboardEvent) {
    if (!rows.length) return;
    if (e.key === "ArrowLeft") setCursor((c) => Math.max(0, (c ?? rows.length - 1) - 1));
    else if (e.key === "ArrowRight") setCursor((c) => (c == null || c + 1 >= rows.length ? null : c + 1));
    else if (e.key === "Escape") setCursor(null);
  }

  const levelMarks =
    !live && recorded
      ? recorded.levels
          .filter((l) => l.t0 != null)
          .map((l) => ({ level: l.level, x: ((l.t0 as number) - t0) / Math.max(1, (rows[rows.length - 1]?.t ?? 1) - t0) }))
      : [];

  return (
    <section aria-label="Lab endpoint telemetry" className="rounded-[6px] border border-line bg-bg-1">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-2.5">
        <div className="flex items-center gap-2 text-[13px]">
          <span className="font-medium text-fg-0">Lab endpoint</span>
          <span className="num text-[11px] text-fg-3">vLLM · Qwen2.5-0.5B · {live ? "localhost:8100" : (recorded?.gpu ?? "")}</span>
        </div>
        {state === "connecting" ? (
          <span className="text-[11px] text-fg-3">connecting…</span>
        ) : live ? (
          <Pill tone="live">live · 1 s</Pill>
        ) : (
          <Pill tone="off">lab offline · showing recorded run</Pill>
        )}
      </header>

      {!live && state !== "connecting" && (
        <p className="border-b border-line px-4 py-2 text-[11px] text-fg-2">
          {recorded ? (
            <>
              Recorded {recorded.started_at.slice(0, 16).replace("T", " ")} UTC · {recorded.config} · concurrency{" "}
              {recorded.levels.map((l) => l.level).join(", ")} · source{" "}
              <a className="num text-fg-1 underline decoration-line-strong underline-offset-2 hover:text-fg-0" href={`/bench`}>
                {recorded.source}
              </a>
              {gpuOnly && lastGpu?.sm_clock_mhz != null && (
                <span className="text-fg-3">
                  {" "}
                  · this host&apos;s GPU right now: <span className="num">{fmt.int(lastGpu.sm_clock_mhz)} MHz</span>,{" "}
                  <span className="num">{fmt.one(lastGpu.power_w)} W</span>
                </span>
              )}
            </>
          ) : recorded === null ? (
            "No recorded run available either."
          ) : (
            "Loading the recorded run…"
          )}
        </p>
      )}

      {rows.length > 0 && (
        <div className="px-4 pt-3 pb-4">
          <div className="flex items-baseline justify-between text-[11px]">
            <span className="text-fg-3">
              GPU power, W · {live ? `last ${rows.length} s` : `whole run, ${Math.round((rows[rows.length - 1].t - t0) || 0)} s`}
            </span>
            <span className="num text-fg-2">
              {tLabel(at)} · <span className="text-fg-0">{fmt.one(row?.power ?? null)} W</span>
            </span>
          </div>
          <div
            role="img"
            tabIndex={0}
            onKeyDown={onKey}
            onPointerLeave={() => setCursor(null)}
            aria-label={`GPU power heat strip, ${rows.length} seconds; latest ${fmt.one(rows[rows.length - 1].power)} W. Arrow keys move the cursor.`}
            className="relative mt-1.5 flex h-7 gap-px"
          >
            {rows.map((r, i) => (
              <div
                key={`${r.t}-${i}`}
                onPointerEnter={() => setCursor(i)}
                className={`h-full flex-1 transition-colors duration-200 ${i === at && cursor != null ? "outline outline-1 outline-fg-1" : ""}`}
                style={{ background: heatColor(r.power) }}
              />
            ))}
            {levelMarks.map((m) => (
              <span
                key={m.level}
                className="num pointer-events-none absolute -bottom-4 text-[10px] text-fg-3"
                style={{ left: `${m.x * 100}%` }}
              >
                c={m.level}
              </span>
            ))}
          </div>
          <div className={`flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-fg-3 ${levelMarks.length ? "mt-6" : "mt-2"}`}>
            {["idle", ...HEAT_BANDS.slice(1).map((b, i) => `${HEAT_BANDS[i]}–${b}`), `≥${HEAT_BANDS[HEAT_BANDS.length - 1]}`].map(
              (lab, i) => (
                <span key={lab} className="inline-flex items-center gap-1">
                  <span className="h-2 w-3" style={{ background: i === 0 ? "var(--bg-3)" : `var(--heat-${i})` }} />
                  <span className="num">{lab}</span>
                </span>
              ),
            )}
            <span>W</span>
          </div>

          <div
            className={`mt-4 grid gap-x-5 gap-y-4 ${compact ? "grid-cols-2 sm:grid-cols-3" : "grid-cols-2 sm:grid-cols-4 lg:grid-cols-7"}`}
            onPointerLeave={() => setCursor(null)}
          >
            {METRICS.filter((m) => !compact || m.key !== "waiting").map((m) => (
              <div
                key={m.key}
                className="min-w-0 border-l border-line pl-3"
                onPointerMove={(e) => {
                  const r = e.currentTarget.getBoundingClientRect();
                  const f = (e.clientX - r.left) / r.width;
                  setCursor(Math.max(0, Math.min(rows.length - 1, Math.round(f * (rows.length - 1)))));
                }}
              >
                <div className="text-[11px] text-fg-3">{m.label}</div>
                <div className="num mt-0.5 text-[17px] text-fg-0">
                  {m.format(row?.[m.key] ?? null)}
                  {m.unit && <span className="ml-1 text-[11px] text-fg-3">{m.unit}</span>}
                </div>
                <Spark rows={rows} k={m.key} cursor={at} />
              </div>
            ))}
          </div>
          <p className="mt-3 text-[10px] leading-relaxed text-fg-3">
            {live
              ? "Read every second from vLLM /metrics (prefix-cache hit and tokens/s over the last second; blank when idle) and NVML on the serving host."
              : recorded?.notes.join(" ")}
          </p>
        </div>
      )}

      {!live && state !== "connecting" && rows.length === 0 && recorded !== undefined && (
        <p className="px-4 py-6 text-[12px] text-fg-2">Lab endpoint offline and no recorded telemetry found.</p>
      )}
    </section>
  );
}
