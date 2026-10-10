"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Verdict } from "@/components/guard/verdict";

type GNode = { key: string; kind: string; label: string };
type GEdge = { src: string; dst: string; kind: string };
type Impact = {
  type: "impact";
  categories: string[];
  touched: { key: string; via: string }[];
  affected: string[];
  selected: { key: string; reason: string; path: string[] }[];
  skipped: { key: string; reason: string }[];
  full_suite_size: number;
  fell_back_to_full: boolean;
  changed: string[];
  nodes: GNode[];
  edges: GEdge[];
  seconds?: number;
};
type Check = { key: string; state: "queued" | "running" | "pass" | "fail" | "warn" | "skip" | "error"; seconds?: number; detail?: string; startedAt?: number };
type JobInfo = { job_id: string | null; kind?: string; status?: string; created_at?: string; error?: string | null };
type LogLine = { id: string; msg: string; ts: string; level: string };

const RING_MS = 200; // one graph ring lights up every RING_MS after the impact arrives

/** BFS distance from the touched nodes over undirected edges: 0 = changed, 1 = one hop away... */
function rings(imp: Impact): Map<string, number> {
  const adj = new Map<string, string[]>();
  for (const e of imp.edges) {
    adj.set(e.src, [...(adj.get(e.src) ?? []), e.dst]);
    adj.set(e.dst, [...(adj.get(e.dst) ?? []), e.src]);
  }
  const d = new Map<string, number>();
  const q: string[] = [];
  for (const t of imp.touched) {
    if (d.has(t.key)) continue;
    d.set(t.key, 0);
    q.push(t.key);
  }
  while (q.length) {
    const k = q.shift() as string;
    for (const n of adj.get(k) ?? []) {
      if (d.has(n)) continue;
      d.set(n, (d.get(k) ?? 0) + 1);
      q.push(n);
    }
  }
  for (const n of imp.nodes) if (!d.has(n.key)) d.set(n.key, 1);
  return d;
}

function ImpactGraph({ imp, lit, focus }: { imp: Impact; lit: number; focus: string[] | null }) {
  const dist = useMemo(() => rings(imp), [imp]);
  const maxD = Math.max(0, ...dist.values());
  const cols = maxD + 1;
  const NW = 150;
  const NH = 44;
  const GX = 30;
  const GY = 14;
  const byCol = Array.from({ length: cols }, (_, c) =>
    imp.nodes.filter((n) => dist.get(n.key) === c).sort((a, b) => a.kind.localeCompare(b.kind) || a.key.localeCompare(b.key)),
  );
  const rows = Math.max(1, ...byCol.map((c) => c.length));
  const W = cols * NW + (cols - 1) * GX + 8;
  const H = rows * NH + (rows - 1) * GY + 8;
  const pos = new Map<string, { x: number; y: number }>();
  byCol.forEach((col, c) => {
    // changed code on the right, what it reaches (up to the workflow) to the left
    const x = 4 + (cols - 1 - c) * (NW + GX);
    const off = ((rows - col.length) * (NH + GY)) / 2;
    col.forEach((n, r) => pos.set(n.key, { x, y: 4 + off + r * (NH + GY) }));
  });
  const touched = new Set(imp.touched.map((t) => t.key));
  const onPath = focus ? new Set(focus) : null;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" style={{ maxHeight: 360 }} role="img" aria-label={`Impact graph: ${imp.touched.length} changed nodes, ${imp.nodes.length} nodes reached`}>
      {imp.edges.map((e) => {
        const a = pos.get(e.src);
        const b = pos.get(e.dst);
        if (!a || !b) return null;
        const on = (dist.get(e.src) ?? 9) <= lit && (dist.get(e.dst) ?? 9) <= lit;
        const hl = onPath ? onPath.has(e.src) && onPath.has(e.dst) : false;
        const [l, r] = a.x <= b.x ? [a, b] : [b, a];
        const x1 = l.x + NW;
        const x2 = r.x;
        const y1 = l.y + NH / 2;
        const y2 = r.y + NH / 2;
        const d = x2 > x1 ? `M${x1},${y1} C${(x1 + x2) / 2},${y1} ${(x1 + x2) / 2},${y2} ${x2},${y2}` : `M${a.x + NW / 2},${a.y + NH} L${b.x + NW / 2},${b.y}`;
        return (
          <path
            key={`${e.src}->${e.dst}`}
            d={d}
            fill="none"
            stroke={hl ? "var(--fg-1)" : on ? "var(--line-strong)" : "var(--line)"}
            strokeWidth={hl ? 2 : 1}
            className="transition-[stroke] duration-200"
          />
        );
      })}
      {imp.nodes.map((n) => {
        const p = pos.get(n.key);
        if (!p) return null;
        const d = dist.get(n.key) ?? 0;
        const on = d <= lit;
        const hot = touched.has(n.key) && on;
        const dim = onPath && !onPath.has(n.key);
        return (
          <g key={n.key} className={`transition-opacity duration-200 ${dim ? "opacity-40" : "opacity-100"}`}>
            <title>{`${n.kind}: ${n.key}${touched.has(n.key) ? " (changed in this PR)" : ` (${d} hop${d === 1 ? "" : "s"} from the change)`}`}</title>
            <rect
              x={p.x}
              y={p.y}
              width={NW}
              height={NH}
              rx={4}
              fill={hot ? "var(--ember-lo)" : "var(--bg-2)"}
              stroke={hot ? "var(--ember)" : on ? "var(--line-strong)" : "var(--line)"}
              strokeWidth={hot ? 1.5 : 1}
              className="transition-[fill,stroke] duration-200"
            />
            <text x={p.x + 8} y={p.y + 16} fontSize={10} fill={hot ? "var(--ember-hi)" : "var(--fg-3)"} className="num">
              {n.kind}
              {hot ? " · changed" : ""}
            </text>
            <text x={p.x + 8} y={p.y + 34} fontSize={12} fill={on ? "var(--fg-0)" : "var(--fg-3)"} className="transition-[fill] duration-200">
              {n.label.length > 19 ? `${n.label.slice(0, 18)}…` : n.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

/** The run's job events as a terminal: newest at the bottom, time since the first event. */
function RunLog({ log, live }: { log: LogLine[]; live: boolean }) {
  const ref = useRef<HTMLOListElement | null>(null);
  useEffect(() => {
    const el = ref.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [log.length]);
  if (!log.length) return null;
  const t0 = new Date(log[0].ts).getTime();
  return (
    <div className="mt-4 rounded-[4px] border border-line bg-bg-0">
      <div className="flex justify-between border-b border-line px-3 py-1.5 text-[10px] text-fg-3">
        <span>run log · job events</span>
        <span className="num">{log.length} events</span>
      </div>
      <ol ref={ref} className="num max-h-[220px] overflow-y-auto px-3 py-2 text-[11px] leading-[1.75]" aria-live="off">
        {log.map((l) => (
          <li key={l.id} className={`line-in grid grid-cols-[52px_1fr] gap-2 ${l.level === "error" ? "text-bad" : "text-fg-2"}`}>
            <span className="text-fg-3">+{((new Date(l.ts).getTime() - t0) / 1000).toFixed(1)}s</span>
            <span className="break-words">{l.msg.split("\n")[0]}</span>
          </li>
        ))}
        {live && (
          <li className="grid grid-cols-[52px_1fr] gap-2 text-fg-3">
            <span />
            <span className="caret">▍</span>
          </li>
        )}
      </ol>
    </div>
  );
}

function StateBadge({ c, now }: { c: Check; now: number }) {
  if (c.state === "queued") return <span className="num text-[11px] text-fg-3">queued</span>;
  if (c.state === "running")
    // elapsed only once the clock has ticked: never a negative or invented time
    return (
      <span className="num inline-flex items-center gap-1.5 text-[11px] text-fg-1">
        <span className="h-1.5 w-1.5 rounded-full bg-fg-1 motion-safe:animate-pulse" aria-hidden="true" />
        running {c.startedAt && now > c.startedAt ? `${((now - c.startedAt) / 1000).toFixed(0)} s` : ""}
      </span>
    );
  return <Verdict v={c.state} />;
}

/**
 * Watch a Guard run: the impact graph lights up the changed nodes and what they reach,
 * then each selected check flips from queued to running to its verdict, with its time.
 * Everything is replayed from the run's job events (stored, so a finished run replays too).
 */
export function GuardLive({ scenario }: { scenario: string }) {
  const [job, setJob] = useState<JobInfo | null>(null);
  const [imp, setImp] = useState<Impact | null>(null);
  const [checks, setChecks] = useState<Check[]>([]);
  const [verdict, setVerdict] = useState<{ conclusion: string; title: string; seconds?: number } | null>(null);
  const [lit, setLit] = useState(-1);
  const [focus, setFocus] = useState<string[] | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState<LogLine[]>([]);
  const [now, setNow] = useState(0);
  const es = useRef<EventSource | null>(null);
  const timers = useRef<number[]>([]);

  const attach = useCallback((j: JobInfo) => {
    if (!j.job_id) return;
    es.current?.close();
    timers.current.forEach(clearTimeout);
    setJob(j);
    setImp(null);
    setChecks([]);
    setVerdict(null);
    setLit(-1);
    setLog([]);
    const s = new EventSource(`/api/guard/runs/${j.job_id}/events`);
    es.current = s;
    s.addEventListener("progress", (ev) => {
      const me = ev as MessageEvent;
      const p = JSON.parse(me.data);
      const d = p.data ?? {};
      setLog((prev) => (prev.some((l) => l.id === me.lastEventId) ? prev : [...prev, { id: me.lastEventId, msg: p.msg, ts: p.ts, level: p.level }]));
      if (d.type === "impact") {
        const im = d as Impact;
        setImp(im);
        setChecks(im.selected.map((x) => ({ key: x.key, state: "queued" })));
        const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        const depth = Math.max(0, ...rings(im).values());
        timers.current = reduce
          ? [window.setTimeout(() => setLit(depth), 0)]
          : Array.from({ length: depth + 1 }, (_, k) => window.setTimeout(() => setLit(k), 120 + k * RING_MS));
      } else if (d.type === "check_start") {
        const at = new Date(p.ts).getTime();
        setChecks((cs) => cs.map((c) => (c.key === d.key ? { ...c, state: "running", startedAt: at } : c)));
      } else if (d.type === "check_done") {
        setChecks((cs) => cs.map((c) => (c.key === d.key ? { ...c, state: d.verdict, seconds: d.seconds, detail: d.detail } : c)));
      } else if (d.type === "verdict") {
        setVerdict({ conclusion: d.conclusion, title: d.title, seconds: d.seconds });
      }
    });
    s.addEventListener("status", (ev) => {
      const st = JSON.parse((ev as MessageEvent).data);
      setJob(st);
      s.close();
    });
  }, []);

  useEffect(() => {
    let alive = true;
    fetch(`/api/guard/runs/latest?scenario=${scenario}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => alive && j?.job_id && attach(j))
      .catch(() => {});
    const t = timers.current;
    return () => {
      alive = false;
      es.current?.close();
      t.forEach(clearTimeout);
    };
  }, [scenario, attach]);

  const running = job != null && (job.status === "queued" || job.status === "running");
  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(id);
  }, [running]);

  async function start() {
    setBusy(true);
    setMsg(null);
    const r = await fetch("/api/guard/runs", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ scenario }),
    }).catch(() => null);
    setBusy(false);
    if (!r) return setMsg("API unreachable.");
    const b = await r.json().catch(() => ({}));
    if (r.status === 201) return attach({ job_id: b.job_id, kind: "guard.local", status: "queued", created_at: new Date().toISOString() });
    if (r.status === 409 && b.detail?.job_id) return attach({ job_id: b.detail.job_id, status: "running" });
    setMsg(typeof b.detail === "string" ? b.detail : (b.detail?.msg ?? `Could not start (${r.status}).`));
  }

  const done = checks.filter((c) => !["queued", "running"].includes(c.state)).length;
  const sumS = checks.reduce((a, c) => a + (c.seconds ?? 0), 0);

  return (
    <section aria-labelledby="guard-live" className="rounded-[6px] border border-line bg-bg-1">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3">
        <div>
          <h2 id="guard-live" className="text-[14px] font-medium text-fg-0">
            Guard, live
          </h2>
          <p className="text-[11px] text-fg-3">
            {job?.job_id ? (
              <>
                {running ? "Running" : "Last run"} · {job.kind === "guard.pr" ? "GitHub PR" : "local, F1 fixture"} ·{" "}
                {job.created_at ? new Date(job.created_at).toLocaleString() : ""} · job {job.job_id.slice(0, 8)}
                {job.status === "failed" && job.error ? <span className="text-bad"> · failed: {job.error.slice(0, 120)}</span> : null}
              </>
            ) : (
              "No run recorded for this PR yet. Runs on the laptop runner: sandboxed tests plus the lab endpoint."
            )}
          </p>
        </div>
        <button
          onClick={start}
          disabled={busy || running}
          className="rounded-[3px] border border-line-strong px-3 py-1.5 text-[13px] text-fg-0 transition-colors duration-150 hover:bg-bg-3 disabled:cursor-not-allowed disabled:text-fg-3"
        >
          {running ? "Running…" : busy ? "Starting…" : "Run Guard on this PR"}
        </button>
      </header>
      {msg && <p className="border-b border-line px-4 py-2 text-[12px] text-warn">{msg}</p>}

      {job?.job_id && !imp && (
        <p className="num px-4 py-6 text-[12px] text-fg-3">{running ? "waiting for the runner to claim the job…" : "This run recorded no impact analysis."}</p>
      )}

      {imp && (
        <div className="grid gap-0 lg:grid-cols-[1.25fr_1fr]">
          <div className="border-b border-line p-4 lg:border-r lg:border-b-0">
            <div className="flex flex-wrap items-baseline justify-between gap-2 text-[11px] text-fg-3">
              <span>
                Impact · {imp.changed.length} file{imp.changed.length === 1 ? "" : "s"} changed · categories{" "}
                <span className="num text-fg-1">{imp.categories.join(", ") || "none"}</span>
              </span>
              {imp.seconds != null && <span className="num">{imp.seconds.toFixed(2)} s</span>}
            </div>
            <div className="mt-3">
              {imp.nodes.length ? (
                <ImpactGraph imp={imp} lit={lit} focus={focus} />
              ) : (
                <p className="text-[12px] text-fg-2">No graph node touched{imp.fell_back_to_full ? "; fell back to the full suite" : ""}.</p>
              )}
            </div>
            <p className="mt-2 text-[10px] text-fg-3">
              Right: what the diff changed. Leftward: what those nodes reach, up to the workflow. Hover a check to see the
              path that selected it.
            </p>
            <RunLog log={log} live={running} />
          </div>

          <div className="p-4">
            <div className="flex items-baseline justify-between text-[11px] text-fg-3">
              <span>
                Checks <span className="num text-fg-1">{done}</span>/{checks.length} · {checks.length} of {imp.full_suite_size} selected
              </span>
              <span className="num">{sumS.toFixed(1)} s</span>
            </div>
            <ol className="mt-2" aria-live="polite">
              {checks.map((c) => {
                const sel = imp.selected.find((s) => s.key === c.key);
                return (
                  <li
                    key={c.key}
                    tabIndex={0}
                    onPointerEnter={() => setFocus(sel?.path ?? null)}
                    onPointerLeave={() => setFocus(null)}
                    onFocus={() => setFocus(sel?.path ?? null)}
                    onBlur={() => setFocus(null)}
                    className="group border-b border-line py-2 outline-none focus-visible:bg-bg-2"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="num truncate text-[12px] text-fg-0">{c.key}</span>
                      <span className="flex shrink-0 items-center gap-2">
                        {c.seconds != null && <span className="num text-[11px] text-fg-3">{c.seconds.toFixed(1)} s</span>}
                        <StateBadge c={c} now={now} />
                      </span>
                    </div>
                    {(c.detail || sel) && (
                      <p className="mt-0.5 line-clamp-2 text-[11px] text-fg-3">{c.detail ?? sel?.reason}</p>
                    )}
                  </li>
                );
              })}
            </ol>
            {imp.skipped.length > 0 && (
              <details className="mt-2 text-[11px] text-fg-3">
                <summary className="cursor-pointer text-fg-2">{imp.skipped.length} skipped, with reasons</summary>
                <ul className="mt-1 space-y-1">
                  {imp.skipped.map((s) => (
                    <li key={s.key}>
                      <span className="num text-fg-2">{s.key}</span>: {s.reason}
                    </li>
                  ))}
                </ul>
              </details>
            )}
            {verdict && (
              <div data-guard-verdict role="status" className="line-in mt-3 flex flex-wrap items-center gap-2 rounded-[4px] border border-line-strong bg-bg-2 px-3 py-2 text-[12px]">
                <Verdict v={verdict.conclusion} />
                <span className="text-fg-0">{verdict.title}</span>
                {verdict.seconds != null && <span className="num text-fg-3">· {verdict.seconds.toFixed(0)} s total</span>}
              </div>
            )}
          </div>
        </div>
      )}

    </section>
  );
}
