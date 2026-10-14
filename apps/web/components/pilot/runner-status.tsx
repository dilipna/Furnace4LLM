"use client";

import { useCallback, useEffect, useState } from "react";
import { RECORDED_ONLY } from "@/lib/site";

type RunnerRow = { id: string; queues: string[]; capabilities: Record<string, unknown>; last_seen: string; online: boolean };
type State =
  | { kind: "loading" }
  | { kind: "api-down" }
  | { kind: "ok"; runners: RunnerRow[]; checkedAt: Date };

const ago = (iso: string) => {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 90) return `${Math.round(s)} s ago`;
  if (s < 5400) return `${Math.round(s / 60)} min ago`;
  if (s < 172800) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} days ago`;
};

/** Live availability of the control API and the Guard runner, or, on a recorded-only site, that neither is connected. */
export function RunnerStatus() {
  return RECORDED_ONLY ? <RecordedStatus /> : <LiveRunnerStatus />;
}

function RecordedStatus() {
  const rows = [
    ["Control API", "Not deployed on this site. Every page shows recorded results."],
    ["Guard runner", "Not connected to this site. Live Guard runs happen on the runner machine during a pilot."],
  ];
  return (
    <div className="rounded-[6px] border border-line-strong bg-bg-1">
      <div className="border-b border-line px-4 py-2.5">
        <span className="text-[12px] text-fg-2">System status: recorded-only site</span>
      </div>
      <ul className="divide-y divide-line">
        {rows.map(([name, detail]) => (
          <li key={name} className="px-4 py-3">
            <div className="flex items-center gap-3">
              <span aria-hidden="true" className="h-2 w-2 shrink-0 rounded-full border border-dashed border-fg-3" />
              <span className="text-[13px] text-fg-0">{name}</span>
              <span className="num ml-auto text-[11.5px] text-fg-2">NOT HERE</span>
            </div>
            <p className="mt-1 pl-5 text-[12px] text-fg-2">{detail}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

function LiveRunnerStatus() {
  const [st, setSt] = useState<State>({ kind: "loading" });
  const check = useCallback(() => {
    fetch("/api/runners", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((runners: RunnerRow[]) => setSt({ kind: "ok", runners, checkedAt: new Date() }))
      .catch(() => setSt({ kind: "api-down" }));
  }, []);
  useEffect(() => {
    check();
    const t = setInterval(check, 30_000);
    return () => clearInterval(t);
  }, [check]);

  const guard = st.kind === "ok" ? st.runners.filter((r) => r.queues.includes("runner")) : [];
  const online = guard.find((r) => r.online);
  const lastSeen = guard[0]?.last_seen;

  const rows: { name: string; state: "up" | "down" | "unknown"; detail: string; fix?: string }[] = [
    {
      name: "Control API",
      state: st.kind === "loading" ? "unknown" : st.kind === "api-down" ? "down" : "up",
      detail: st.kind === "api-down" ? "Not answering. Pages show recorded results only." : "Answering",
      fix: st.kind === "api-down" ? "Local: uv run poe api (port 8010). Hosted: check the API service's logs; free instances sleep and take about a minute to wake." : undefined,
    },
    {
      name: "Guard runner",
      state: st.kind !== "ok" ? "unknown" : online ? "up" : "down",
      detail:
        st.kind !== "ok"
          ? "Unknown while the API is down"
          : online
            ? `Online${typeof online.capabilities.gpu === "string" ? ` · ${online.capabilities.gpu}` : ""}${online.capabilities.docker ? " · Docker" : ""}`
            : lastSeen
              ? `Offline · last seen ${ago(lastSeen)}`
              : "No runner has ever connected",
      fix:
        st.kind === "ok" && !online
          ? "On the GPU machine: start Docker, then uv run poe runner. Live Guard runs and repairs wait in the queue until a runner claims them."
          : undefined,
    },
  ];

  return (
    <div className="rounded-[6px] border border-line-strong bg-bg-1" aria-live="polite">
      <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
        <span className="text-[12px] text-fg-2">System status, live</span>
        <button onClick={check} className="text-[12px] text-fg-2 underline-offset-2 hover:text-fg-0 hover:underline">
          Check again
        </button>
      </div>
      <ul className="divide-y divide-line">
        {rows.map((r) => (
          <li key={r.name} className="px-4 py-3">
            <div className="flex items-center gap-3">
              <span
                aria-hidden="true"
                className={`h-2 w-2 shrink-0 rounded-full ${r.state === "up" ? "bg-ok" : r.state === "down" ? "bg-bad" : "border border-dashed border-fg-3"}`}
              />
              <span className="text-[13px] text-fg-0">{r.name}</span>
              <span className="num ml-auto text-[11.5px] text-fg-2">{r.state === "up" ? "UP" : r.state === "down" ? "DOWN" : "…"}</span>
            </div>
            <p className="mt-1 pl-5 text-[12px] text-fg-2">{r.detail}</p>
            {r.fix && <p className="mt-1 pl-5 text-[12px] text-fg-1">→ {r.fix}</p>}
          </li>
        ))}
      </ul>
      {st.kind === "ok" && (
        <p className="border-t border-line px-4 py-2 text-[11px] text-fg-3">
          Checked {st.checkedAt.toLocaleTimeString()} · refreshes every 30 s
        </p>
      )}
    </div>
  );
}
