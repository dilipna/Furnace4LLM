/** Confidence as a number plus a 5-tick meter. No gauges, no donuts. */
export function Confidence({ value }: { value: number }) {
  const ticks = Math.round(value * 5);
  return (
    <span className="inline-flex items-center gap-1.5" title={`confidence ${value.toFixed(2)}`}>
      <span className="num text-[12px] text-fg-1">{value.toFixed(2)}</span>
      <span className="flex gap-[2px]" aria-hidden="true">
        {Array.from({ length: 5 }, (_, i) => (
          <span key={i} className={`h-[9px] w-[3px] rounded-[1px] ${i < ticks ? "bg-fg-1" : "bg-line-strong"}`} />
        ))}
      </span>
    </span>
  );
}

const GLYPH = {
  direct_observation: { g: "◆", label: "observed directly in evidence" },
  inference: { g: "◇", label: "inferred" },
  contested: { g: "⇋", label: "sources disagree; all values shown" },
} as const;

export function Provenance({ kind }: { kind: keyof typeof GLYPH }) {
  const { g, label } = GLYPH[kind];
  return (
    <span className={kind === "contested" ? "text-warn" : "text-fg-3"} title={label} aria-label={label}>
      {g}
    </span>
  );
}
