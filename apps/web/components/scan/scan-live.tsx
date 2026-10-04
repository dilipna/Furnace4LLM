"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

interface Line {
  id: string;
  stage: string;
  level: string;
  msg: string;
  ts: string;
}

/** Streams real job events for a running scan; refreshes the page when it finishes. */
export function ScanLive({ scanId }: { scanId: string }) {
  const router = useRouter();
  const [lines, setLines] = useState<Line[]>([]);
  const [failed, setFailed] = useState<string | null>(null);

  useEffect(() => {
    const es = new EventSource(`/api/scans/${scanId}/events`);
    es.addEventListener("progress", (ev) => {
      const d = JSON.parse((ev as MessageEvent).data);
      setLines((prev) =>
        prev.some((l) => l.id === (ev as MessageEvent).lastEventId)
          ? prev
          : [...prev, { id: (ev as MessageEvent).lastEventId, stage: d.stage, level: d.level, msg: d.msg, ts: d.ts }],
      );
    });
    es.addEventListener("status", (ev) => {
      const d = JSON.parse((ev as MessageEvent).data);
      es.close();
      if (d.status === "succeeded") router.refresh();
      else setFailed(d.error ?? "Scan failed");
    });
    es.onerror = () => {
      // EventSource reconnects automatically; nothing to do.
    };
    return () => es.close();
  }, [scanId, router]);

  return (
    <div className="rounded-panel border border-line bg-bg-1">
      <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
        <span className="text-[13px] font-medium">{failed ? "Scan failed" : "Scanning"}</span>
        {!failed && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-ember" aria-hidden="true" />}
      </div>
      <ol className="num max-h-[420px] overflow-y-auto px-4 py-3 text-[12px] leading-[1.9]">
        {lines.length === 0 && <li className="text-fg-3">waiting for a worker…</li>}
        {lines.map((l) => (
          <li key={l.id} className="grid grid-cols-[56px_88px_1fr] gap-2">
            <span className="text-fg-3">
              +{((new Date(l.ts).getTime() - new Date(lines[0].ts).getTime()) / 1000).toFixed(1)}s
            </span>
            <span className={l.level === "error" ? "text-bad" : "text-fg-2"}>{l.stage}</span>
            <span className={l.level === "error" ? "text-bad" : "text-fg-1"}>{l.msg}</span>
          </li>
        ))}
        {failed && <li className="mt-2 text-bad">{failed}</li>}
      </ol>
    </div>
  );
}
