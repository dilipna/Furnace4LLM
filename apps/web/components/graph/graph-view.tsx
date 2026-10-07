"use client";

import { useMemo, useState } from "react";

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

/** Layered behavior-to-code graph. Hover highlights everything connected (both directions). */
export function GraphView({ nodes, edges }: { nodes: GNode[]; edges: GEdge[] }) {
  const [hover, setHover] = useState<string | null>(null);
  const [sel, setSel] = useState<string | null>(null);

  const layout = useMemo(() => {
    const byKey = new Map(nodes.map((n) => [n.key, n]));
    const cols: GNode[][] = COLUMNS.map(() => []);
    for (const n of nodes) cols[colOf(n.kind)].push(n);
    const neighbors = new Map<string, string[]>();
    for (const e of edges) {
      if (!byKey.has(e.src) || !byKey.has(e.dst)) continue;
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
    return { cols, xy, neighbors, height, byKey };
  }, [nodes, edges]);

  const focus = hover ?? sel;
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
            const on = lit ? lit.has(e.src) && lit.has(e.dst) : false;
            const [l, r] = a.x <= b.x ? [a, b] : [b, a];
            if (l.x === r.x) {
              // same column (e.g. a call between functions): a small arc on the left edge
              const y1 = l.y + NODE_H / 2;
              const y2 = r.y + NODE_H / 2;
              return (
                <path key={i} d={`M${l.x},${y1} C${l.x - 22},${y1} ${l.x - 22},${y2} ${l.x},${y2}`} fill="none"
                  stroke={on ? "var(--ember)" : "var(--line-strong)"} strokeWidth={on ? 1.5 : 1} opacity={lit && !on ? 0.25 : 1} />
              );
            }
            const x1 = l.x + COL_W;
            const y1 = l.y + NODE_H / 2;
            const x2 = r.x;
            const y2 = r.y + NODE_H / 2;
            const mx = (x1 + x2) / 2;
            return (
              <path key={i} d={`M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`} fill="none"
                stroke={on ? "var(--ember)" : "var(--line-strong)"} strokeWidth={on ? 1.5 : 1} opacity={lit && !on ? 0.25 : 1} />
            );
          })}
          {layout.cols.flat().map((n) => {
            const p = layout.xy.get(n.key);
            if (!p) return null;
            const on = !lit || lit.has(n.key);
            const isSel = sel === n.key;
            return (
              <g
                key={n.key}
                transform={`translate(${p.x},${p.y})`}
                opacity={on ? 1 : 0.3}
                onPointerEnter={() => setHover(n.key)}
                onPointerLeave={() => setHover(null)}
                onClick={() => setSel(isSel ? null : n.key)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setSel(isSel ? null : n.key);
                  }
                }}
                onFocus={() => setHover(n.key)}
                onBlur={() => setHover(null)}
                tabIndex={0}
                role="button"
                aria-label={`${n.kind} ${n.label}`}
                aria-pressed={isSel}
                className="cursor-pointer outline-none"
              >
                <rect width={COL_W} height={NODE_H} rx="3" fill={isSel ? "var(--ember-lo)" : "var(--bg-2)"} stroke={isSel || (hover === n.key) ? "var(--ember)" : "var(--line)"} />
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
        {!selected && <p className="text-[12px] text-fg-3">Hover a node to trace its path; click it for details.</p>}
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
                      <button className="text-fg-1 hover:text-ember-hi" onClick={() => setSel(other)}>
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
