const STYLE: Record<string, string> = {
  pass: "text-ok border-ok/40",
  success: "text-ok border-ok/40",
  verified: "text-ok border-ok/40",
  warn: "text-warn border-warn/40",
  neutral: "text-warn border-warn/40",
  fail: "text-bad border-bad/40",
  failure: "text-bad border-bad/40",
  block: "text-bad border-bad/40",
  rejected: "text-bad border-bad/40",
  error: "text-bad border-bad/40",
  skip: "text-fg-2 border-line-strong",
};

const ICON: Record<string, string> = {
  pass: "✓",
  success: "✓",
  verified: "✓",
  warn: "!",
  neutral: "!",
  fail: "✕",
  failure: "✕",
  block: "✕",
  rejected: "✕",
  error: "✕",
  skip: "–",
};

/** Status tag: icon and word are always shown, so state never depends on color alone. */
export function Verdict({ v }: { v: string }) {
  return (
    <span className={`num inline-block rounded-[3px] border px-1.5 py-px text-[11px] uppercase ${STYLE[v] ?? "text-fg-2 border-line"}`}>
      {ICON[v] && (
        <span aria-hidden="true" className="mr-1">
          {ICON[v]}
        </span>
      )}
      {v}
    </span>
  );
}
