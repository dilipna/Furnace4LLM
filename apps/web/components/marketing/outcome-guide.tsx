import { Verdict, VERDICT_MEANING } from "@/components/guard/verdict";

export function OutcomeGuide() {
  return (
    <section aria-labelledby="outcomes-h" className="mx-auto w-full max-w-[1100px] px-4 py-12 sm:px-6">
      <h2 id="outcomes-h" className="scroll-mt-20 font-display text-3xl font-semibold">Read the result, then choose the next step</h2>
      <p className="mt-4 text-fg-2">Missing evidence, uncertain measurements and a detected regression mean different things. A proposed fix always needs human review.</p>
      <dl className="mt-6 divide-y divide-line">
        {VERDICT_MEANING.map(([state, meaning]) => (
          <div key={state} className="grid gap-3 py-4 md:grid-cols-[300px_1fr]">
            <dt><Verdict v={state} /></dt>
            <dd className="text-sm leading-relaxed text-fg-2">{meaning}</dd>
          </div>
        ))}
      </dl>
      <details className="mt-6 rounded border border-line-strong p-4 text-sm leading-relaxed text-fg-2">
        <summary className="cursor-pointer text-fg-0">Exact acceptance rules and scope</summary>
        <p className="mt-3">The performance gate compares run-level geometric-mean time to first token using a 90% interval: PASS if its upper bound is at most +10%; BLOCK if its lower bound exceeds +10% and the point estimate exceeds +25%; WARN for a smaller certain regression; otherwise INCONCLUSIVE.</p>
        <p className="mt-3">Measured repair verification requires at least three interleaved runs per revision, every executed sandbox check passing, a 90% interval upper bound below 0% versus the slow change and below +25% versus the original. These are repair acceptance rules, not the gate’s PASS rule. Required comparisons must be complete, finite and consistent with their verdicts; failure-rate blocks cannot be overridden by favorable latency. Missing comparisons cannot verify performance. Skipped checks do not establish answer equivalence.</p>
        <a className="mt-3 inline-block underline" href="https://github.com/dilipna/Furnace4LLM/blob/main/docs/repair-verification.md">Implementation contract and limitations</a>
      </details>
    </section>
  );
}
