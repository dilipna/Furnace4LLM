"use client";

import { useEffect, useRef, useState } from "react";
import { checkPrefix, exampleSnapshots, MAX_BYTES } from "@/lib/prefix-check";

export function PrefixChecker() {
  const [base, setBase] = useState("");
  const [head, setHead] = useState("");
  const [result, setResult] = useState<ReturnType<typeof checkPrefix> | null>(null);
  const [error, setError] = useState("");
  const feedback = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (result || error) feedback.current?.scrollIntoView({ block: "nearest" });
  }, [result, error]);
  function resetResult() { setResult(null); setError(""); }
  function example(fixed: boolean) {
    const sample = exampleSnapshots(fixed);
    setBase(sample.base); setHead(sample.head); setError("");
    setResult(checkPrefix(sample.base, sample.head));
  }
  const button = "rounded-md border border-line px-4 py-2 text-sm hover:bg-bg-2 focus-visible:outline-2 focus-visible:outline-ember";
  return <section aria-label="Compare prompt snapshots" className="mt-8 space-y-6">
    <div className="flex flex-wrap gap-3">
      <button className={button} onClick={() => example(false)}>Try a regression</button>
      <button className={button} onClick={() => example(true)}>Try the repair</button>
      <button className={button} onClick={() => { setBase(""); setHead(""); resetResult(); }}>Clear prompts</button>
    </div>
    <p id="snapshot-help" className="text-sm leading-relaxed text-fg-2">Paste rendered requests as JSONL: one object per line with a <code>messages</code> array of text <code>role</code> / <code>content</code> fields. Use 2–200 distinct final user questions, matched in the same order in both snapshots. Limit: 2 MiB each. Examples above use synthetic prompts.</p>
    <div className="grid gap-5 md:grid-cols-2">
      {(["Base", "Head"] as const).map(label => <div key={label} className="min-w-0">
        <label htmlFor={`snapshot-${label}`} className="mb-2 block text-sm font-medium">{label} snapshot</label>
        <textarea id={`snapshot-${label}`} aria-describedby="snapshot-help" value={label === "Base" ? base : head}
          onChange={event => { const value = event.target.value; if (new TextEncoder().encode(value).length > MAX_BYTES) { setError(`${label}: limit is 2 MiB per snapshot.`); setResult(null); return; } (label === "Base" ? setBase : setHead)(value); resetResult(); }}
          className="h-64 w-full resize-y rounded-lg border border-line bg-bg-1 p-4 font-mono text-xs leading-relaxed focus:border-ember focus:outline-none" spellCheck={false} autoComplete="off" autoCorrect="off" autoCapitalize="off" placeholder={'{"messages":[{"role":"system","content":"Your stable instructions"},{"role":"user","content":"A distinct question"}]}'} />
      </div>)}
    </div>
    <button className="rounded-md bg-ember px-5 py-3 text-sm font-semibold text-bg-0 hover:bg-ember-hi focus-visible:outline-2 focus-visible:outline-fg-0" onClick={() => {
      try { setResult(checkPrefix(base, head)); setError(""); } catch (err) { setResult(null); setError(err instanceof Error ? err.message : "Could not compare these snapshots."); }
    }}>Compare prefixes</button>
    <div ref={feedback}>
    {error && <p role="alert" className="rounded-lg border border-ember p-4 text-sm">{error}</p>}
    <div role="status" aria-live="polite" aria-atomic="true">
      {result && <div className="rounded-xl border border-line bg-bg-1 p-6">
        <p className="font-mono text-xs text-ember">STRUCTURAL CHECK · {result.status}</p>
        <h2 className="mt-2 text-2xl font-semibold">{result.status === "PASS" ? "Prefix preserved" : result.status === "FAIL" ? "Prefix shortened" : "Baseline is too weak to protect"}</h2>
        <dl className="mt-5 grid grid-cols-2 gap-5 text-sm sm:grid-cols-4">{[["Base shared chars", result.baseShared], ["Head shared chars", result.headShared], ["Required (90% of base)", result.required], ["Requests per snapshot", result.requests]].map(([label, value]) => <div key={label}><dt className="text-fg-2">{label}</dt><dd className="mt-1 font-mono text-lg">{value}</dd></div>)}</dl>
        <p className="mt-5 text-sm leading-relaxed text-fg-2">{result.status === "FAIL" ? "Look for timestamps, IDs, or other per-request values before your stable instructions. Moving them later can preserve the common prefix; check answer quality separately." : result.status === "INCONCLUSIVE" ? "The baseline shares little beyond its role label. Provide representative requests with stable instructions before interpreting this check." : "The head retains at least 90% of the baseline’s shared leading characters. This does not establish a cache hit, lower latency, or equivalent answers."}</p>
      </div>}
    </div>
    </div>
  </section>;
}
