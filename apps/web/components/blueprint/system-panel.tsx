import { Confidence, Provenance } from "@/components/ui/confidence";
import type { AppSpec, Claim } from "@/lib/types";

function prov<T>(c: Claim<T>) {
  return c.status === "contested" ? "contested" : c.observation;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[96px_1fr] gap-3 border-t border-line py-2.5 first:border-t-0">
      <dt className="text-[12px] text-fg-3">{label}</dt>
      <dd className="min-w-0 text-[13px] text-fg-1">{children}</dd>
    </div>
  );
}

function ClaimLine<T>({ c, render }: { c: Claim<T>; render?: (v: T) => React.ReactNode }) {
  return (
    <span className="flex items-center justify-between gap-2">
      <span className="flex min-w-0 items-center gap-1.5">
        <Provenance kind={prov(c)} />
        <span className="truncate" title={String(c.value)}>
          {render ? render(c.value) : String(c.value)}
        </span>
      </span>
      <Confidence value={c.confidence} />
    </span>
  );
}

export function SystemPanel({ spec }: { spec: AppSpec }) {
  const engine = spec.endpoints[0]?.engine;
  const flags = spec.endpoints[0]?.serving_flags ?? {};
  const rel = spec.reliability_existing;
  const has = (k: keyof typeof rel) => rel[k]?.length > 0;
  return (
    <div className="space-y-6">
      {spec.contradictions.length > 0 && (
        <section className="rounded-panel border border-warn/40 bg-bg-1">
          <h2 className="border-b border-line px-4 py-2.5 text-[13px] font-medium text-warn">
            ⇋ {spec.contradictions.length} contradiction{spec.contradictions.length === 1 ? "" : "s"} between sources
          </h2>
          <ul className="divide-y divide-line">
            {spec.contradictions.map((c) => (
              <li key={`${c.subject_key}:${c.predicate}`} className="px-4 py-3">
                <p className="text-[12px] text-fg-3">
                  <span className="num text-fg-2">{c.predicate}</span> of <span className="num">{c.subject_key}</span>
                </p>
                <ul className="mt-2 space-y-2">
                  {c.values.map((v, i) => (
                    <li key={i}>
                      <div className="flex items-center justify-between gap-2">
                        <span className="num truncate text-[13px] text-fg-0">{String(v.value)}</span>
                        <Confidence value={v.confidence} />
                      </div>
                      <p className="mt-0.5 text-[12px] leading-snug text-fg-2">
                        <span className="num text-fg-3">{v.sources.join(" + ")} · </span>
                        {v.rationale}
                      </p>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="rounded-panel border border-line bg-bg-1">
        <h2 className="border-b border-line px-4 py-2.5 text-[13px] font-medium">Detected system</h2>
        <dl className="px-4 py-1">
          {spec.purpose && (
            <Field label="Purpose">
              <ClaimLine c={spec.purpose} />
            </Field>
          )}
          <Field label="Languages">
            <span className="num text-[12px]">
              {Object.entries(spec.architecture.languages)
                .map(([k, n]) => `${k} ${n}`)
                .join(" · ") || "–"}
            </span>
          </Field>
          {spec.architecture.frameworks.length > 0 && (
            <Field label="Frameworks">{spec.architecture.frameworks.map((f) => String(f.value)).join(", ")}</Field>
          )}
          <Field label="Routes">
            <ul className="space-y-0.5">
              {spec.routes.map((r) => (
                <li key={r.key} className="num text-[12px]">
                  <span className="text-fg-3">{r.method}</span> {r.path}
                </li>
              ))}
              {!spec.routes.length && <li className="text-fg-3">none detected</li>}
            </ul>
          </Field>
          {spec.llm_calls.map((c) => (
            <Field key={c.key} label="LLM call">
              <p className="num text-[12px] text-fg-2">
                {c.locator.path}:{c.locator.line_start}
              </p>
              {c.model && (
                <div className="mt-1">
                  <ClaimLine c={c.model} />
                </div>
              )}
              <p className="mt-1 text-[12px] text-fg-2">
                {c.streaming?.value ? "streaming" : "non-streaming"} · {c.has_timeout ? "timeout set" : "no timeout"}
                {c.structured_output ? " · structured output" : ""}
                {c.tools_passed ? " · tool calling" : ""}
              </p>
            </Field>
          ))}
          {engine && (
            <Field label="Serving">
              <ClaimLine c={engine} />
              {Object.keys(flags).length > 0 && (
                <p className="num mt-1 flex flex-wrap gap-x-2 text-[11.5px] leading-relaxed text-fg-3">
                  {Object.entries(flags).map(([k, v]) => (
                    <span key={k} className="whitespace-nowrap">
                      {v === true ? `--${k}` : `--${k}=${String(v)}`}
                    </span>
                  ))}
                </p>
              )}
            </Field>
          )}
          {spec.rag && (
            <Field label="RAG">
              <ClaimLine c={spec.rag.present} render={(v) => (v ? "yes" : "no")} />
              {spec.rag.retrievers.map((r) => (
                <p key={r.key} className="num mt-1 text-[12px] text-fg-2">
                  {String(r.store.value)} · {r.locator.path}
                  {r.top_k ? ` · top_k=${r.top_k.value}` : ""}
                </p>
              ))}
            </Field>
          )}
          <Field label="Tools">
            {spec.tools.length ? (
              <ul className="space-y-1.5">
                {spec.tools.map((t) => (
                  <li key={t.key}>
                    <span className="num text-[12px] text-fg-0">{t.name}</span>{" "}
                    <span className="text-[12px] text-fg-2">
                      · {String(t.side_effect.value)} side effect ·{" "}
                      <span className={t.approval_gate.value ? "text-ok" : "text-bad"}>
                        {t.approval_gate.value ? "approval gate" : "no approval gate"}
                      </span>
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <span className="text-fg-3">no side-effecting tools detected</span>
            )}
          </Field>
          <Field label="Existing">
            <ul className="space-y-0.5 text-[12px]">
              {(["tests", "evals", "tracing", "timeouts", "retries"] as const).map((k) => (
                <li key={k} className="flex justify-between gap-2">
                  <span className="text-fg-2">{k}</span>
                  <span className={has(k) ? "text-fg-1" : "text-fg-3"}>
                    {has(k) ? rel[k].map((c) => String(c.value)).join(", ") : "none found"}
                  </span>
                </li>
              ))}
            </ul>
          </Field>
        </dl>
      </section>
    </div>
  );
}
