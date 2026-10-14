// One vocabulary for every outcome Furnace shows. Icon and word are always rendered, so a
// state never depends on color alone, and the five easily confused ones stay distinct:
// passed, failed, inconclusive (measured, the data cannot decide), skipped (decided not to
// run, with a reason) and not run (never attempted). A skip is never a pass.
type Tone = "ok" | "warn" | "bad" | "unsure" | "idle";

const TONE: Record<Tone, string> = {
  ok: "text-ok border-ok/40",
  warn: "text-warn border-warn/40",
  bad: "text-bad border-bad/40",
  unsure: "text-unsure border-unsure/50 border-dashed",
  idle: "text-fg-2 border-line-strong border-dashed",
};

const KIND: Record<string, [Tone, string]> = {
  pass: ["ok", "✓"],
  success: ["ok", "✓"],
  verified: ["ok", "✓"],
  warn: ["warn", "!"],
  neutral: ["warn", "!"],
  fail: ["bad", "✕"],
  failure: ["bad", "✕"],
  block: ["bad", "✕"],
  rejected: ["bad", "✕"],
  error: ["bad", "✕"],
  inconclusive: ["unsure", "?"],
  skip: ["idle", "–"],
  skipped: ["idle", "–"],
  not_run: ["idle", "○"],
  unsupported: ["idle", "⊘"],
  pending: ["idle", "…"],
};

export const VERDICT_MEANING: [string, string][] = [
  ["pass", "Measured, and the whole interval is inside the tolerance (or the check passed)."],
  ["fail", "A check failed, or a regression was measured beyond the tolerance."],
  ["block", "Perf gate: slower than the block threshold (25%) with the whole interval above 10%."],
  ["inconclusive", "Measured, but the interval is too wide to decide. Not a pass and not a fail."],
  ["skip", "Deliberately not run, with the reason shown (for example: no judge key). Not a pass."],
  ["not_run", "Never attempted: the precondition was missing (no runner, no GitHub App)."],
  ["unsupported", "Outside what Furnace can repair; it says so instead of guessing."],
];

export function Verdict({ v }: { v: string }) {
  const [tone, icon] = KIND[v] ?? ["idle", ""];
  return (
    <span className={`num inline-block rounded-[3px] border px-1.5 py-px text-[11px] uppercase ${TONE[tone]}`}>
      {icon && (
        <span aria-hidden="true" className="mr-1">
          {icon}
        </span>
      )}
      {v.replace("_", " ")}
    </span>
  );
}
