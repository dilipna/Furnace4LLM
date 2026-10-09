"use client";

import { useEffect, useMemo, useRef, useState } from "react";

export type GNode = { key: string; kind: string; label: string; attrs: Record<string, unknown>; confidence: number };
export type GEdge = { kind: string; src: string; dst: string; confidence: number };

const COLUMNS: { title: string; kinds: string[] }[] = [
  { title: "Workflows", kinds: ["workflow"] },
  { title: "Capabilities", kinds: ["capability"] },
  { title: "Routes & code", kinds: ["route", "component"] },
  { title: "Prompt · model · endpoint · tools", kinds: ["prompt", "model", "endpoint", "serving_config", "retriever", "tool", "security_boundary"] },
  { title: "Configuration", kinds: ["config_key", "dependency"] },
];
const COL_W = 176;
const GAP = 40;
const TAG: Record<string, string> = {
  workflow: "flow",
  capability: "cap",
  route: "route",
  component: "code",
  prompt: "prompt",
  model: "model",
  endpoint: "api",
  serving_config: "serve",
  retriever: "rag",
  tool: "tool",
  security_boundary: "gate",
  config_key: "cfg",
  dependency: "dep",
};
const ROW_H = 34;
const NODE_H = 24;
const TOP = 34;

const colOf = (kind: string) => {
  const i = COLUMNS.findIndex((c) => c.kinds.includes(kind));
  return i >= 0 ? i : COLUMNS.length - 1;
};
const clip = (s: string, n = 19) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);
const STEP_MS = 160; // one hop of the path trace

type Layout = { byKey: Map<string, GNode>; neighbors: Map<string, string[]>; calls: Set<string> };

/** Hop distance from `start`, moving only leftward (dir -1) or rightward (dir 1) by column. */
function walk(start: string, dir: -1 | 1, layout: Layout): Map<string, number> {
  const dist = new Map([[start, 0]]);
  const c0 = colOf(layout.byKey.get(start)?.kind ?? "");
  let frontier = [start];
  let d = 0;
  while (frontier.length) {
    d += 1;
    const next: string[] = [];
    for (const k of frontier) {
      const ck = colOf(layout.byKey.get(k)?.kind ?? "");
      for (const m of layout.neighbors.get(k) ?? []) {
        const cm = colOf(layout.byKey.get(m)?.kind ?? "");
        // within a column (code calling code) follow the call: callers upstream, callees down
        const sameColOk = cm !== ck || layout.calls.has(dir === 1 ? `${k}>${m}` : `${m}>${k}`);
        if (!dist.has(m) && sameColOk && (cm - ck) * dir >= 0 && (cm - c0) * dir >= 0) {
          dist.set(m, d);
          next.push(m);
        }
      }
    }
    frontier = next;
  }
  return dist;
}

/** The selected node's path in trace order: upstream hops first, then downstream. */
function trace(start: string, layout: Layout) {
  const up = walk(start, -1, layout);
  const down = walk(start, 1, layout);
  const upMax = Math.max(0, ...up.values());
  const level = new Map<string, number>(up);
  for (const [k, d] of down) if (d > 0 && !level.has(k)) level.set(k, upMax + d);
  return { level, max: Math.max(0, ...level.values()), up, upMax };
}

/** Layered behavior-to-code graph. Hover highlights everything connected (both directions). */
export function GraphView({ nodes, edges }: { nodes: GNode[]; edges: GEdge[] }) {
  const [hover, setHover] = useState<string | null>(null);
  const [sel, setSel] = useState<string | null>(null);

  const layout = useMemo(() => {
    const byKey = new Map(nodes.map((n) => [n.key, n]));
    const cols: GNode[][] = COLUMNS.map(() => []);
    for (const n of nodes) cols[colOf(n.kind)].push(n);
    const neighbors = new Map<string, string[]>();
    const calls = new Set<string>();
    for (const e of edges) {
      if (!byKey.has(e.src) || !byKey.has(e.dst)) continue;
      calls.add(`${e.src}>${e.dst}`);
      neighbors.set(e.src, [...(neighbors.get(e.src) ?? []), e.dst]);
      neighbors.set(e.dst, [...(neighbors.get(e.dst) ?? []), e.src]);
    }
    // Barycenter ordering, left to right, to reduce crossings.
    const pos = new Map<string, number>();
    cols[0].sort((a, b) => a.label.localeCompare(b.label)).forEach((n, i) => pos.set(n.key, i));
    for (let c = 1; c < cols.length; c++) {
      const score = (n: GNode) => {
        const ps = (neighbors.get(n.key) ?? []).map((k) => pos.get(k)).filter((v): v is number => v != null);
        return ps.length ? ps.reduce((a, b) => a + b, 0) / ps.length : Number.MAX_SAFE_INTEGER;
      };
      cols[c].sort((a, b) => score(a) - score(b) || a.kind.localeCompare(b.kind) || a.label.localeCompare(b.label));
      cols[c].forEach((n, i) => pos.set(n.key, i));
    }
    const xy = new Map<string, { x: number; y: number }>();
    cols.forEach((col, c) => col.forEach((n, i) => xy.set(n.key, { x: c * (COL_W + GAP), y: TOP + i * ROW_H })));
    const height = TOP + Math.max(1, ...cols.map((c) => c.length)) * ROW_H + 8;
    return { cols, xy, neighbors, calls, height, byKey };
  }, [nodes, edges]);

  const [step, setStep] = useState(0);
  const timers = useRef<number[]>([]);
  const tr = useMemo(() => (sel ? trace(sel, layout) : null), [sel, layout]);
  function select(k: string | null) {
    setSel(k);
    setStep(0);
  }
  // Animate the selected node's path: upstream hops light first, then downstream.
  useEffect(() => {
    timers.current.forEach(clearTimeout);
    if (!tr) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    timers.current = reduce
      ? [window.setTimeout(() => setStep(tr.max), 0)]
      : Array.from({ length: tr.max }, (_, i) => window.setTimeout(() => setStep(i + 1), (i + 1) * STEP_MS));
    const t = timers.current;
    return () => t.forEach(clearTimeout);
  }, [tr]);

  // Hover previews connections instantly; the selection's trace is animated.
  const focus = hover && hover !== sel ? hover : null;
  const lit = useMemo(() => {
    if (!focus) return null;
    // Connected component reachable from the focused node along edges in both directions,
    // restricted to moving monotonically left or right so the highlight reads as a path.
    const out = new Set([focus]);
    const c0 = colOf(layout.byKey.get(focus)?.kind ?? "");
    for (const dir of [-1, 1]) {
      let frontier = [focus];
      while (frontier.length) {
        const next: string[] = [];
        for (const k of frontier) {
          const ck = colOf(layout.byKey.get(k)?.kind ?? "");
          for (const m of layout.neighbors.get(k) ?? []) {
            const cm = colOf(layout.byKey.get(m)?.kind ?? "");
            if (!out.has(m) && (cm - ck) * dir >= 0 && (cm - c0) * dir >= 0) {
              out.add(m);
              next.push(m);
            }
          }
        }
        frontier = next;
      }
    }
    return out;
  }, [focus, layout]);

  const width = COLUMNS.length * COL_W + (COLUMNS.length - 1) * GAP;
  const selected = sel ? layout.byKey.get(sel) : undefined;
  const selEdges = sel ? edges.filter((e) => e.src === sel || e.dst === sel) : [];

  return (
    <div className="grid gap-6 2xl:grid-cols-[minmax(0,1fr)_320px]">
      <div className="overflow-x-auto rounded-[6px] border border-line bg-bg-1 p-4">
        <svg width={width} height={layout.height} role="img" aria-label="Behavior-to-code reliability graph">
          {COLUMNS.map((c, i) => (
            <text key={c.title} x={i * (COL_W + GAP)} y={14} fontSize="11" fill="var(--fg-3)">
              {c.title}
            </text>
          ))}
          {edges.map((e, i) => {
            const a = layout.xy.get(e.src);
            const b = layout.xy.get(e.dst);
            if (!a || !b) return null;
            const ls = tr?.level.get(e.src);
            const ld = tr?.level.get(e.dst);
            const traced = !lit && ls != null && ld != null && Math.max(ls, ld) <= step;
            const on = lit ? lit.has(e.src) && lit.has(e.dst) : traced;
            const dim = (lit && !on) || (tr != null && !lit && !traced);
            // draw from the node already reached toward the next hop
            const upLeg = tr != null && ls != null && ld != null && Math.max(ls, ld) <= tr.upMax;
            const drawCls = traced ? (upLeg ? "trace-draw-rev" : "trace-draw") : "";
            const [l, r] = a.x <= b.x ? [a, b] : [b, a];
            if (l.x === r.x) {
              // same column (e.g. a call between functions): a small arc on the left edge
              const y1 = l.y + NODE_H / 2;
              const y2 = r.y + NODE_H / 2;
              return (
                <path key={i} d={`M${l.x},${y1} C${l.x - 22},${y1} ${l.x - 22},${y2} ${l.x},${y2}`} fill="none"
                  stroke={on ? "var(--fg-1)" : "var(--line-strong)"} strokeWidth={on ? 1.5 : 1} opacity={dim ? 0.25 : 1} pathLength={1} className={drawCls} />
              );
            }
            const x1 = l.x + COL_W;
            const y1 = l.y + NODE_H / 2;
            const x2 = r.x;
            const y2 = r.y + NODE_H / 2;
            const mx = (x1 + x2) / 2;
            return (
              <path key={i} d={`M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`} fill="none"
                stroke={on ? "var(--fg-1)" : "var(--line-strong)"} strokeWidth={on ? 1.5 : 1} opacity={dim ? 0.25 : 1} pathLength={1} className={drawCls} />
            );
          })}
          {layout.cols.flat().map((n) => {
            const p = layout.xy.get(n.key);
            if (!p) return null;
            const nl = tr?.level.get(n.key);
            const on = lit ? lit.has(n.key) : tr ? nl != null && nl <= step : true;
            const isSel = sel === n.key;
            return (
              <g
                key={n.key}
                transform={`translate(${p.x},${p.y})`}
                opacity={on ? 1 : 0.3}
                style={{ transition: "opacity 180ms ease-out" }}
                onPointerEnter={() => setHover(n.key)}
                onPointerLeave={() => setHover(null)}
                onClick={() => select(isSel ? null : n.key)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    select(isSel ? null : n.key);
                  } else if (e.key === "Escape") select(null);
                }}
                onFocus={() => setHover(n.key)}
                onBlur={() => setHover(null)}
                tabIndex={0}
                role="button"
                aria-label={`${n.kind} ${n.label}`}
                aria-pressed={isSel}
                className="cursor-pointer outline-none"
              >
                <rect
                  width={COL_W}
                  height={NODE_H}
                  rx="3"
                  fill={isSel ? "var(--bg-3)" : "var(--bg-2)"}
                  stroke={isSel ? "var(--fg-0)" : hover === n.key ? "var(--fg-2)" : tr && on && !lit ? "var(--line-strong)" : "var(--line)"}
                  strokeWidth={isSel ? 1.5 : 1}
                />
                <text x="8" y="16" fontSize="11" fill="var(--fg-3)" className="num">
                  {TAG[n.kind] ?? n.kind.slice(0, 5)}
                </text>
                <text x="52" y="16" fontSize="12" fill="var(--fg-0)">
                  {clip(n.label)}
                  <title>{n.label}</title>
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      <aside className="2xl:sticky 2xl:top-6 2xl:self-start" aria-live="polite">
        {!selected && (
          <p className="text-[12px] text-fg-3">
            Hover a node to see what it connects to. Click it (or Tab, then Enter) to trace its path, upstream then
            downstream; Esc clears.
          </p>
        )}
        {selected && tr && (
          <ol className="mb-3 max-h-[340px] overflow-y-auto rounded-[6px] border border-line bg-bg-1 p-3 text-[12px]" aria-label="Traced path, in order">
            {[...tr.level.entries()]
              .sort((x, y) => x[1] - y[1])
              .map(([k, lv]) => {
                const n = layout.byKey.get(k);
                const up = k !== sel && tr.up.has(k);
                return (
                  <li key={k} className={`flex gap-2 transition-opacity duration-200 ${lv <= step ? "opacity-100" : "opacity-30"}`}>
                    <span className="num w-8 shrink-0 text-fg-3">{k === sel ? "·" : up ? "↑" : "↓"}</span>
                    <span className="num w-12 shrink-0 text-fg-3">{TAG[n?.kind ?? ""] ?? n?.kind}</span>
                    <span className="truncate text-fg-1">{n?.label ?? k}</span>
                  </li>
                );
              })}
          </ol>
        )}
        {selected && (
          <div className="rounded-[6px] border border-line bg-bg-1 p-4">
            <div className="text-[11px] text-fg-3">{selected.kind}</div>
            <div className="mt-0.5 text-[14px] text-fg-0">{selected.label}</div>
            <div className="num mt-1 text-[11px] break-all text-fg-3">{selected.key}</div>
            <div className="num mt-2 text-[12px] text-fg-2">confidence {selected.confidence.toFixed(2)}</div>
            {Object.keys(selected.attrs).length > 0 && (
              <dl className="mt-3 space-y-1 text-[12px]">
                {Object.entries(selected.attrs).map(([k, v]) => (
                  <div key={k} className="flex gap-2">
                    <dt className="w-28 shrink-0 text-fg-3">{k}</dt>
                    <dd className="num break-all text-fg-1">{typeof v === "object" ? JSON.stringify(v) : String(v)}</dd>
                  </div>
                ))}
              </dl>
            )}
            {selEdges.length > 0 && (
              <ul className="mt-3 space-y-1 border-t border-line pt-3 text-[12px]">
                {selEdges.map((e, i) => {
                  const other = e.src === sel ? e.dst : e.src;
                  return (
                    <li key={i}>
                      <span className="text-fg-3">{e.src === sel ? `${e.kind} →` : `← ${e.kind}`}</span>{" "}
                      <button className="text-fg-1 hover:text-fg-0 hover:underline" onClick={() => select(other)}>
                        {layout.byKey.get(other)?.label ?? other}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        )}
      </aside>
    </div>
  );
}
