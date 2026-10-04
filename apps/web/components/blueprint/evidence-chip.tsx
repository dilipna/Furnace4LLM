"use client";

import { useState } from "react";
import type { Evidence } from "@/lib/types";

function label(e: Evidence): string {
  const l = e.locator;
  if (l.path && l.line_start) return `${l.path}:${l.line_start}`;
  return l.path ?? l.url ?? l.symbol ?? e.extractor;
}

export function EvidenceList({ ids, evidence }: { ids: string[]; evidence: Record<string, Evidence> }) {
  const [open, setOpen] = useState<string | null>(null);
  const items = ids.map((id) => ({ id, e: evidence[id] })).filter((x) => x.e);
  if (!items.length) return null;
  const active = items.find((x) => x.id === open);
  return (
    <div className="mt-2">
      <div className="flex flex-wrap gap-1.5">
        {items.map(({ id, e }) => (
          <button
            key={id}
            type="button"
            onClick={() => setOpen(open === id ? null : id)}
            aria-expanded={open === id}
            className={`num h-6 rounded-ctl border px-2 text-[11.5px] transition-colors duration-150 ${
              open === id ? "border-fg-3 bg-bg-3 text-fg-0" : "border-line bg-bg-2 text-fg-2 hover:border-line-strong hover:text-fg-1"
            }`}
          >
            {e.observation === "inference" ? "◇ " : ""}
            {label(e)}
          </button>
        ))}
      </div>
      {active && (
        <div className="mt-2 overflow-hidden rounded-ctl border border-line bg-bg-0">
          <div className="flex items-center justify-between border-b border-line px-3 py-1.5 text-[11px] text-fg-3">
            <span className="num">{label(active.e)}</span>
            <span className="num">
              {active.e.extractor} · {active.e.observation === "inference" ? "inferred" : "observed"}
            </span>
          </div>
          <pre className="num overflow-x-auto px-3 py-2 text-[12px] leading-relaxed whitespace-pre text-fg-1">{active.e.excerpt}</pre>
        </div>
      )}
    </div>
  );
}
