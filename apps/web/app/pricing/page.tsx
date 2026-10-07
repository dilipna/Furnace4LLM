import Link from "next/link";
import { AppHeader } from "@/components/ui/app-header";

const PLANS = [
  {
    name: "Scan",
    price: "Free",
    cadence: "",
    body: "Reconstruct an existing LLM app from its repository: call sites, models, serving, RAG, tools and gates, with evidence and confidence. Shareable Blueprint.",
    items: ["Public GitHub repos and ZIP uploads", "Behavior-to-code reliability graph", "Contradictions between docs and code", "Prioritized Blueprint"],
    cta: { label: "Scan a repository", href: "/" },
  },
  {
    name: "Forge",
    price: "$15",
    cadence: "once per repository",
    body: "A draft pull request that installs only what the Blueprint justified, validated in a sandbox before it is opened.",
    items: ["Deterministic checks and targeted judges", "Prompt extraction (byte-identical)", "Workload and benchmark configs", "CI gate; you review and merge"],
    cta: null,
  },
  {
    name: "Guard",
    price: "$25",
    cadence: "first month, then $10/mo",
    body: "Pull request checks that run only the evals and benchmarks a change can affect, and failing-test-first repairs.",
    items: ["Graph-targeted check selection", "Quality and latency gates on your endpoint", "Regression test written before any fix", "Verified draft repair PRs"],
    cta: null,
  },
];

export default function PricingPage() {
  return (
    <div className="flex min-h-full flex-col">
      <AppHeader active="/pricing" />
      <main className="mx-auto w-full max-w-[1200px] flex-1 px-4 py-12 sm:px-6">
        <p className="num text-[12px] tracking-wide text-ember">BETA PRICING</p>
        <h1 className="mt-3 font-display text-[36px] font-semibold tracking-[-0.02em]">Pay for changes, not for dashboards.</h1>
        <p className="mt-3 max-w-[640px] text-[14px] text-fg-2">
          Models, keys and GPUs stay yours: evals and benchmarks run on your endpoints with your keys. Furnace never merges
          and never touches production.
        </p>
        <div className="mt-10 grid border-y border-line md:grid-cols-3">
          {PLANS.map((p, i) => (
            <section
              key={p.name}
              aria-labelledby={`plan-${p.name}`}
              className={`flex flex-col py-8 md:px-8 ${i === 0 ? "md:pl-0" : "border-t border-line md:border-t-0 md:border-l"}`}
            >
              <h2 id={`plan-${p.name}`} className="font-display text-[20px] font-semibold">
                {p.name}
              </h2>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="font-display text-[36px] font-semibold tracking-[-0.02em]">{p.price}</span>
                <span className="text-[12px] text-fg-3">{p.cadence}</span>
              </div>
              <p className="mt-3 text-[13px] leading-relaxed text-fg-1">{p.body}</p>
              <ul className="mt-5 space-y-2 text-[13px] text-fg-2">
                {p.items.map((t) => (
                  <li key={t} className="flex gap-2">
                    <span className="text-fg-3" aria-hidden="true">
                      –
                    </span>
                    {t}
                  </li>
                ))}
              </ul>
              <div className="mt-auto pt-8">
                {p.cta ? (
                  <Link href={p.cta.href} className="inline-block rounded-[3px] bg-ember px-4 py-2 text-[13px] font-medium text-bg-0 hover:bg-ember-hi">
                    {p.cta.label}
                  </Link>
                ) : (
                  <p className="text-[12px] text-fg-3">In private beta: checkout is not open yet.</p>
                )}
              </div>
            </section>
          ))}
        </div>
      </main>
    </div>
  );
}
