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
  functional_only: ["unsure", "?"],
  action_required: ["warn", "!"],
  interrupted: ["warn", "!"],
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
  ["functional_only", "Executed functional tests passed, but performance was not measured. Next: configure the endpoint and measure before claiming a speed improvement; review behavior changes."],
  ["verified", "Repair passed its executed tests and measured acceptance rules. Next: review the draft and its semantic changes; Furnace never merges it."],
  ["pass", "This check passed. For the performance gate, the entire 90% interval is at or below +10%. Next: inspect other checks and skips; this is not proof of answer quality."],
  ["fail", "An executed check failed. Next: inspect its evidence and fix the cause before proceeding."],
  ["block", "Regression detected: the estimate exceeds +25% and the entire 90% interval exceeds +10%. Next: investigate or test a supported repair."],
  ["inconclusive", "Performance was measured, but uncertainty crosses the +10% tolerance. Next: inspect the workload and collect more representative measurements. This is not a pass."],
  ["action_required", "Evaluation was interrupted by an error or timeout. Next: inspect logs and restore the prerequisite. Queued jobs retry up to their attempt limit; then need intervention. No completed performance result is implied."],
  ["skip", "Deliberately not measured or tested, with a reason such as no judge key. Next: supply the prerequisite if needed. A skip is not a pass."],
  ["not_run", "No attempt was made. Next: configure the missing runner or integration and start an evaluation."],
  ["unsupported", "Outside supported analysis or repair scope. Next: inspect the refusal and review manually; do not weaken the sandbox to force a result."],
];

export function Verdict({ v }: { v: string }) {
  const [tone, icon] = KIND[v] ?? ["idle", ""];
  return (
    <span className={`num inline-block rounded-[3px] border px-1.5 py-px text-[11px] ${v === "functional_only" ? "" : "uppercase"} ${TONE[tone]}`}>
      {icon && (
        <span aria-hidden="true" className="mr-1">
          {icon}
        </span>
      )}
      {v === "functional_only" ? "Functionally tested; performance unverified" : v === "action_required" ? "Interrupted" : v.replaceAll("_", " ")}
    </span>
  );
}
