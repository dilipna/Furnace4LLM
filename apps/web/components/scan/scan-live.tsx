"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

interface Line {
  id: string;
  stage: string;
  level: string;
  msg: string;
  ts: number;
  data: Record<string, unknown>;
}

const STAGES = ["fetch", "extract", "reconcile", "graph", "blueprint", "done"];

/** Counters read from event payloads; each changes only when an event reports it. */
function counts(lines: Line[]) {
  const out: { label: string; value: number | null; at: string | null }[] = [
    { label: "evidence facts", value: null, at: null },
    { label: "claims", value: null, at: null },
    { label: "graph nodes", value: null, at: null },
    { label: "graph edges", value: null, at: null },
    { label: "findings", value: null, at: null },
  ];
  for (const l of lines) {
    const d = l.data;
    const set = (i: number, v: unknown) => {
      if (typeof v === "number") {
        out[i].value = v;
        out[i].at = l.id;
      }
    };
    set(0, d.facts);
    set(1, d.claims);
    set(2, d.nodes);
    set(3, d.edges);
    if (d.by_priority && typeof d.by_priority === "object") {
      set(4, Object.values(d.by_priority as Record<string, number>).reduce((a, b) => a + b, 0));
    }
  }
  return out;
}

/**
 * The scan as a terminal: job events typed in as they arrive, elapsed time per stage, and
 * counters that step when an event reports them. Live while the scan runs; afterwards the
 * same component replays the stored events as the scan log.
 */
export function ScanLive({ scanId, finished = false }: { scanId: string; finished?: boolean }) {
  const router = useRouter();
  const [lines, setLines] = useState<Line[]>([]);
  const [failed, setFailed] = useState<string | null>(null);
  const [complete, setComplete] = useState(finished);
  const [now, setNow] = useState(0);
  const box = useRef<HTMLOListElement | null>(null);

  useEffect(() => {
    const es = new EventSource(`/api/scans/${scanId}/events`);
    const timers: number[] = [];
    let firstTs: number | null = null;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    es.addEventListener("progress", (ev) => {
      const me = ev as MessageEvent;
      const d = JSON.parse(me.data);
      const line = { id: me.lastEventId, stage: d.stage, level: d.level, msg: d.msg, ts: new Date(d.ts).getTime(), data: d.data ?? {} };
      const add = () => setLines((prev) => (prev.some((l) => l.id === line.id) ? prev : [...prev, line]));
      if (!finished || reduce) return add();
      // replay of a finished scan: each line appears at its recorded offset (real timing)
      firstTs ??= line.ts;
      timers.push(window.setTimeout(add, line.ts - firstTs));
    });
    es.addEventListener("status", (ev) => {
      const d = JSON.parse((ev as MessageEvent).data);
      es.close();
      setComplete(true);
      if (d.status === "succeeded") {
        // hold the finished log on screen briefly before the Blueprint replaces it
        if (!finished) window.setTimeout(() => router.refresh(), 900);
      } else setFailed(d.error ?? "Scan failed");
    });
    return () => {
      es.close();
      timers.forEach(clearTimeout);
    };
  }, [scanId, router, finished]);

  useEffect(() => {
    if (complete) return;
    const id = setInterval(() => setNow(Date.now()), 200);
    return () => clearInterval(id);
  }, [complete]);

  useEffect(() => {
    const el = box.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [lines.length]);

  const t0 = lines[0]?.ts ?? 0;
  const firstAt = new Map<string, number>();
  for (const l of lines) if (!firstAt.has(l.stage)) firstAt.set(l.stage, l.ts);
  const seen = STAGES.filter((s) => firstAt.has(s));
  const last = lines[lines.length - 1];
  const stageRows = seen.map((s, i) => {
    const start = firstAt.get(s) as number;
    const next = seen[i + 1] ? (firstAt.get(seen[i + 1]) as number) : null;
    const end = next ?? (complete || s === "done" ? (last?.ts ?? start) : now > start ? now : start);
    return { stage: s, ms: end - start, running: !next && !complete && s !== "done" };
  });
  const total = lines.length ? (complete ? (last?.ts ?? t0) : Math.max(now, last?.ts ?? t0)) - t0 : 0;
  const c = counts(lines);

  return (
    <div className="rounded-[6px] border border-line bg-bg-0">
      <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
        <span className="num text-[12px] text-fg-1">
          {failed ? "scan failed" : complete ? "scan log" : "scanning"} · {(total / 1000).toFixed(1)} s
        </span>
        {!complete && <span className="h-1.5 w-1.5 rounded-full bg-fg-1 motion-safe:animate-pulse" aria-hidden="true" />}
      </div>

      <div className="grid grid-cols-2 gap-x-4 gap-y-2 border-b border-line px-4 py-3 sm:grid-cols-5">
        {c.map((x) => (
          <div key={x.label}>
            <div className="text-[10px] text-fg-3">{x.label}</div>
            <div key={x.at ?? "none"} className={`num text-[15px] ${x.value == null ? "text-fg-3" : "line-in text-fg-0"}`}>
              {x.value == null ? "–" : x.value.toLocaleString()}
            </div>
          </div>
        ))}
      </div>

      <div className="grid gap-0 md:grid-cols-[180px_1fr]">
        <ol className="num border-b border-line px-4 py-3 text-[11px] leading-[1.9] md:border-r md:border-b-0" aria-label="Stages">
          {STAGES.filter((s) => s !== "done").map((s) => {
            const r = stageRows.find((x) => x.stage === s);
            return (
              <li key={s} className={`flex justify-between ${r ? "text-fg-1" : "text-fg-3"}`}>
                <span>
                  <span aria-hidden="true" className="mr-1.5 inline-block w-2">
                    {r ? (r.running ? "›" : "✓") : ""}
                  </span>
                  {s}
                </span>
                <span className={r?.running ? "text-fg-0" : "text-fg-3"}>{r ? `${(r.ms / 1000).toFixed(2)} s` : ""}</span>
              </li>
            );
          })}
        </ol>
        <ol ref={box} className="num max-h-[360px] overflow-y-auto px-4 py-3 text-[12px] leading-[1.9]" aria-live="polite">
          {lines.length === 0 && <li className="text-fg-3">waiting for a worker…</li>}
          {lines.map((l) => (
            <li key={l.id} className="grid grid-cols-[56px_80px_1fr] gap-2">
              <span className="text-fg-3">+{((l.ts - t0) / 1000).toFixed(2)}s</span>
              <span className={l.level === "error" ? "text-bad" : "text-fg-3"}>{l.stage}</span>
              <span className={`type-in ${l.level === "error" ? "text-bad" : "text-fg-1"}`}>{l.msg}</span>
            </li>
          ))}
          {!complete && (
            <li className="grid grid-cols-[56px_80px_1fr] gap-2 text-fg-2">
              <span />
              <span />
              <span className="caret" aria-hidden="true">
                ▍
              </span>
            </li>
          )}
          {failed && <li className="mt-2 text-bad">{failed}</li>}
        </ol>
      </div>
    </div>
  );
}

/** The finished scan's log, replayed from its stored events when opened. */
export function ScanLog({ scanId }: { scanId: string }) {
  const [open, setOpen] = useState(false);
  return (
    <details className="mt-6" onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary className="cursor-pointer text-[12px] text-fg-2 hover:text-fg-0">Scan log: replay the stage timings</summary>
      {open && (
        <div className="mt-3 max-w-[960px]">
          <ScanLive scanId={scanId} finished />
        </div>
      )}
    </details>
  );
}
