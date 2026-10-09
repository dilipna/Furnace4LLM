"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

type Req = { idx: number; level: number; ok: boolean; error: string | null; ttft_ms: number | null; t: number; slo_ok: boolean | null };
type LevelSummary = {
  level: number;
  n: number;
  n_ok: number;
  ttft_p50_ms: number | null;
  ttft_p95_ms: number | null;
  rps: number;
  output_tok_s: number;
  goodput_ratio: number | null;
  prefix_hit_rate: number | null;
  sm_clock_mhz: number | null;
};
type Start = { levels: number[]; requests_per_level: number; slo_ttft_ms: number; workload: string; target: string };
type Done = { run_id: string; saved_to: string; gpu: string | null; levels: LevelSummary[] };
export type Reference = { level: number; on: number | null; off: number | null };

type Phase = "idle" | "starting" | "running" | "done" | "failed";

const W = 640;
const H = 280;
const M = { top: 14, right: 16, bottom: 40, left: 52 };

function p95(xs: number[]): number | null {
  if (!xs.length) return null;
  const s = [...xs].sort((a, b) => a - b);
  const r = 0.95 * (s.length - 1);
  const lo = Math.floor(r);
  return s[lo] + (s[Math.min(lo + 1, s.length - 1)] - s[lo]) * (r - lo);
}

/**
 * "Run it now": a small real FurnaceBench run against the lab endpoint. Each dot is one
 * request's measured TTFT, drawn when that request finishes. Reference ticks are the RQ4
 * medians for the same workload with prefix caching on and off (bench/results).
 */
export function RunNow({ reference, campaign }: { reference: Reference[]; campaign: string | null }) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [msg, setMsg] = useState<string | null>(null);
  const [start, setStart] = useState<Start | null>(null);
  const [reqs, setReqs] = useState<Req[]>([]);
  const [done, setDone] = useState<Done | null>(null);
  const [t0, setT0] = useState<number | null>(null);
  const [now, setNow] = useState(0);
  const [hover, setHover] = useState<number | null>(null);
  const esRef = useRef<EventSource | null>(null);

  const attach = useCallback((runId: string) => {
    esRef.current?.close();
    setReqs([]);
    setDone(null);
    setMsg(null);
    setPhase("running");
    setT0(Date.now());
    const es = new EventSource(`/api/live/bench/${runId}/events`);
    esRef.current = es;
    const data = (ev: Event) => JSON.parse((ev as MessageEvent).data);
    es.addEventListener("start", (ev) => setStart(data(ev)));
    es.addEventListener("request", (ev) => setReqs((p) => [...p, data(ev)]));
    es.addEventListener("done", (ev) => {
      setDone(data(ev));
      setPhase("done");
      es.close();
    });
    es.addEventListener("error", (ev) => {
      const me = ev as MessageEvent;
      if (typeof me.data === "string") {
        setMsg(JSON.parse(me.data).msg);
        setPhase("failed");
        es.close();
      }
    });
  }, []);

  // Pick up a run already in progress (or the last one) so a refresh never loses it.
  useEffect(() => {
    let alive = true;
    fetch("/api/live/bench/latest")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (alive && d?.run_id) attach(d.run_id);
      })
      .catch(() => {});
    return () => {
      alive = false;
      esRef.current?.close();
    };
  }, [attach]);

  useEffect(() => {
    if (phase !== "running") return;
    const id = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(id);
  }, [phase]);

  async function run() {
    setPhase("starting");
    setMsg(null);
    const res = await fetch("/api/live/bench", { method: "POST" }).catch(() => null);
    if (!res) {
      setPhase("failed");
      setMsg("API unreachable.");
      return;
    }
    const body = await res.json().catch(() => ({}));
    if (res.status === 201) return attach(body.run_id);
    if (res.status === 409) {
      const st = await fetch("/api/live/status").then((r) => r.json()).catch(() => null);
      if (st?.active_run) return attach(st.active_run);
    }
    setPhase(reqs.length ? "done" : "idle");
    setMsg(body.detail ?? `Could not start (${res.status}).`);
  }

  const levels = start?.levels ?? reference.map((r) => r.level);
  const perLevel = start?.requests_per_level ?? 20;
  const total = levels.length * perLevel;

  const geo = useMemo(() => {
    const vals = [
      ...reqs.map((r) => r.ttft_ms ?? 0),
      ...reference.flatMap((r) => [r.on ?? 0, r.off ?? 0]),
    ].filter((v) => v > 0);
    const lo = 10;
    const top = Math.max(100, ...vals) * 1.1;
    const hi = [100, 200, 500, 1000, 2000, 5000, 10000].find((t) => t >= top) ?? top;
    const pw = W - M.left - M.right;
    const ph = H - M.top - M.bottom;
    const band = pw / Math.max(1, levels.length);
    const y = (v: number) => M.top + ph - ((Math.log10(Math.max(lo, v)) - Math.log10(lo)) / (Math.log10(hi) - Math.log10(lo))) * ph;
    const cx = (li: number) => M.left + band * (li + 0.5);
    const ticks = [10, 20, 50, 100, 200, 500, 1000, 2000, 5000].filter((t) => t <= hi);
    return { y, cx, band, ticks, ph };
  }, [reqs, reference, levels.length]);

  const byLevel = useMemo(() => {
    const m = new Map<number, Req[]>();
    for (const r of reqs) m.set(r.level, [...(m.get(r.level) ?? []), r]);
    return m;
  }, [reqs]);

  const dots = useMemo(
    () =>
      reqs.map((r) => {
        const li = levels.indexOf(r.level);
        const k = (byLevel.get(r.level) ?? []).indexOf(r);
        const spread = geo.band * 0.56;
        const x = geo.cx(li) - spread / 2 + (perLevel > 1 ? (k / (perLevel - 1)) * spread : spread / 2);
        return { r, x, y: r.ttft_ms != null ? geo.y(r.ttft_ms) : null };
      }),
    [reqs, levels, byLevel, geo, perLevel],
  );

  function onMove(e: React.PointerEvent<SVGRectElement>) {
    const svg = e.currentTarget.ownerSVGElement;
    if (!svg) return;
    const b = svg.getBoundingClientRect();
    const px = ((e.clientX - b.left) / b.width) * W;
    const py = ((e.clientY - b.top) / b.height) * H;
    let best: number | null = null;
    let bd = 24 * 24;
    dots.forEach((d, i) => {
      if (d.y == null) return;
      const dd = (d.x - px) ** 2 + (d.y - py) ** 2;
      if (dd < bd) {
        bd = dd;
        best = i;
      }
    });
    setHover(best);
  }

  const hd = hover != null ? dots[hover] : null;
  const elapsed = t0 && phase === "running" ? (now - t0) / 1000 : null;
  const running = phase === "running" || phase === "starting";

  return (
    <section aria-labelledby="runnow" className="min-w-0 rounded-[6px] border border-line bg-bg-1">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3">
        <div>
          <h2 id="runnow" className="text-[14px] font-medium text-fg-0">
            Run it now
          </h2>
          <p className="text-[11px] text-fg-3">
            {levels.length} concurrency levels × {perLevel} requests on the F1 workload fingerprint, against the lab endpoint.
            One run at a time.
          </p>
        </div>
        <button
          onClick={run}
          disabled={running}
          className="rounded-[3px] bg-ember px-3 py-1.5 text-[13px] font-medium text-bg-0 transition-colors duration-150 hover:bg-ember-hi disabled:cursor-not-allowed disabled:bg-bg-3 disabled:text-fg-2"
        >
          {phase === "starting" ? "Starting…" : phase === "running" ? "Running…" : "Run it now"}
        </button>
      </header>

      <div className="px-4 pt-3">
        <div className="num flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-fg-2" aria-live="polite">
          <span>
            requests <span className="text-fg-0">{reqs.length}</span>/{total}
          </span>
          {elapsed != null && <span>elapsed {elapsed.toFixed(1)} s</span>}
          {reqs.length > 0 && <span>failed {reqs.filter((r) => !r.ok).length}</span>}
          {phase === "done" && done && <span className="text-fg-1">done · run {done.run_id}</span>}
          {msg && <span className={phase === "failed" ? "text-bad" : "text-warn"}>{msg}</span>}
        </div>

        <div className="-mx-1 overflow-x-auto px-1">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="mt-2 h-auto w-full min-w-[520px]"
          role="img"
          tabIndex={0}
          aria-label="Time to first token per request by concurrency, log scale. Arrow keys step through requests; the table view lists every level."
          onKeyDown={(e) => {
            if (!dots.length) return;
            if (e.key === "ArrowRight") setHover((h) => Math.min(dots.length - 1, (h ?? -1) + 1));
            else if (e.key === "ArrowLeft") setHover((h) => Math.max(0, (h ?? dots.length) - 1));
            else if (e.key === "Escape") setHover(null);
          }}
        >
          {geo.ticks.map((t) => (
            <g key={t}>
              <line x1={M.left} x2={W - M.right} y1={geo.y(t)} y2={geo.y(t)} stroke="var(--viz-grid)" strokeWidth={1} />
              <text x={M.left - 8} y={geo.y(t) + 3} textAnchor="end" className="num" fontSize={10} fill="var(--fg-3)">
                {t.toLocaleString()}
              </text>
            </g>
          ))}
          <text x={14} y={M.top + geo.ph / 2} transform={`rotate(-90 14 ${M.top + geo.ph / 2})`} textAnchor="middle" fontSize={10} fill="var(--fg-3)">
            TTFT, ms (log)
          </text>
          {levels.map((lv, li) => {
            const ref = reference.find((r) => r.level === lv);
            const mine = byLevel.get(lv) ?? [];
            const myP95 = mine.length === perLevel ? p95(mine.filter((r) => r.ok && r.ttft_ms != null).map((r) => r.ttft_ms as number)) : null;
            const half = geo.band * 0.34;
            const seg = (v: number | null | undefined, color: string, key: string) =>
              v != null && (
                <line key={key} x1={geo.cx(li) - half} x2={geo.cx(li) + half} y1={geo.y(v)} y2={geo.y(v)} stroke={color} strokeWidth={2} strokeLinecap="round" />
              );
            return (
              <g key={lv}>
                <text x={geo.cx(li)} y={H - M.bottom + 16} textAnchor="middle" className="num" fontSize={11} fill="var(--fg-2)">
                  c={lv}
                </text>
                {seg(ref?.on, "var(--viz-base)", "on")}
                {seg(ref?.off, "var(--viz-focus)", "off")}
                {myP95 != null && (
                  <g className="dot-in">
                    {seg(myP95, "var(--viz-live)", "mine")}
                    <text x={geo.cx(li) + half + 4} y={geo.y(myP95) + 3} fontSize={10} className="num" fill="var(--fg-1)">
                      {Math.round(myP95)}
                    </text>
                  </g>
                )}
              </g>
            );
          })}
          <text x={M.left + (W - M.left - M.right) / 2} y={H - 6} textAnchor="middle" fontSize={10} fill="var(--fg-3)">
            concurrency (closed loop)
          </text>
          {dots.map(
            (d, i) =>
              d.y != null && (
                <circle
                  key={d.r.idx}
                  className="dot-in"
                  cx={d.x}
                  cy={d.y}
                  r={hover === i ? 5 : 4}
                  fill={d.r.ok ? "var(--viz-live)" : "var(--bad)"}
                  stroke="var(--bg-1)"
                  strokeWidth={2}
                />
              ),
          )}
          <rect
            x={M.left}
            y={M.top}
            width={W - M.left - M.right}
            height={geo.ph}
            fill="transparent"
            onPointerMove={onMove}
            onPointerLeave={() => setHover(null)}
          />
          {hd && hd.y != null && (
            <g pointerEvents="none">
              <rect x={Math.min(hd.x + 8, W - 150)} y={Math.max(hd.y - 34, 2)} width={140} height={30} rx={3} fill="var(--bg-3)" stroke="var(--line-strong)" />
              <text x={Math.min(hd.x + 16, W - 142)} y={Math.max(hd.y - 20, 16)} fontSize={10} fill="var(--fg-1)" className="num">
                request {hd.r.idx} · c={hd.r.level}
              </text>
              <text x={Math.min(hd.x + 16, W - 142)} y={Math.max(hd.y - 8, 28)} fontSize={10} fill="var(--fg-0)" className="num">
                TTFT {hd.r.ttft_ms?.toFixed(1)} ms{hd.r.ok ? "" : ` · ${hd.r.error}`}
              </text>
            </g>
          )}
        </svg>
        </div>

        <ul className="flex flex-wrap gap-x-5 gap-y-1 pb-3 text-[11px] text-fg-2">
          <li className="inline-flex items-center gap-1.5">
            <svg width="10" height="10" aria-hidden="true"><circle cx="5" cy="5" r="4" fill="var(--viz-live)" /></svg>
            this run, one dot per request
          </li>
          <li className="inline-flex items-center gap-1.5">
            <span className="h-0.5 w-4 rounded bg-viz-live" aria-hidden="true" />
            this run, p95 (after the level completes)
          </li>
          <li className="inline-flex items-center gap-1.5">
            <span className="h-0.5 w-4 rounded bg-viz-base" aria-hidden="true" />
            RQ4 p95, prefix cache on
          </li>
          <li className="inline-flex items-center gap-1.5">
            <span className="h-0.5 w-4 rounded bg-viz-focus" aria-hidden="true" />
            RQ4 p95, prefix cache off
          </li>
        </ul>
        <p className="pb-3 text-[10px] text-fg-3">
          Reference ticks: median over 3 paired repeats, max-num-seqs 32, bench/results/{campaign ?? "…"}/rq4. The live run
          uses the endpoint as it is configured now (vLLM default: prefix caching on); its measured hit rate is in the table.
        </p>
      </div>

      {(done || reqs.length > 0) && (
        <details className="border-t border-line px-4 py-3" open={phase === "done"}>
          <summary className="cursor-pointer text-[12px] text-fg-1">Table view</summary>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full min-w-[620px] border-collapse text-[12px]">
              <thead>
                <tr className="border-b border-line text-left text-fg-3">
                  {["c", "ok", "TTFT p50", "TTFT p95", "RQ4 p95 on", "req/s", "tok/s", "prefix hit", "GPU MHz"].map((h) => (
                    <th key={h} className="py-1.5 pr-3 text-right font-normal first:text-left">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {levels.map((lv) => {
                  const s = done?.levels.find((l) => l.level === lv);
                  const mine = (byLevel.get(lv) ?? []).filter((r) => r.ok && r.ttft_ms != null).map((r) => r.ttft_ms as number);
                  const ref = reference.find((r) => r.level === lv);
                  const n = (v: number | null | undefined, d = 0) => (v == null ? "–" : v.toFixed(d));
                  return (
                    <tr key={lv} className="num h-7 border-b border-line">
                      <td className="pr-3">{lv}</td>
                      <td className="pr-3 text-right">{s ? `${s.n_ok}/${s.n}` : `${mine.length}/${perLevel}`}</td>
                      <td className="pr-3 text-right">{n(s?.ttft_p50_ms)}</td>
                      <td className="pr-3 text-right text-fg-0">{n(s?.ttft_p95_ms ?? (mine.length === perLevel ? p95(mine) : null))}</td>
                      <td className="pr-3 text-right">{n(ref?.on)}</td>
                      <td className="pr-3 text-right">{n(s?.rps, 2)}</td>
                      <td className="pr-3 text-right">{n(s?.output_tok_s)}</td>
                      <td className="pr-3 text-right">{s?.prefix_hit_rate != null ? `${(s.prefix_hit_rate * 100).toFixed(1)}%` : "–"}</td>
                      <td className="pr-3 text-right">{n(s?.sm_clock_mhz)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {done && (
            <p className="mt-2 text-[10px] text-fg-3">
              {done.gpu ?? "GPU not sampled"} · full records saved to <span className="num">{done.saved_to}</span>
            </p>
          )}
        </details>
      )}
    </section>
  );
}
