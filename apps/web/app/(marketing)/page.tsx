import { BenchStrip } from "@/components/marketing/bench-strip";
import { EvidenceInput } from "@/components/marketing/evidence-input";
import { AppHeader } from "@/components/ui/app-header";

// Live FurnaceBench numbers: render per request, never frozen at build time.
export const dynamic = "force-dynamic";

const QUESTIONS = [
  "Where are the LLM calls, and which models serve them?",
  "Is it RAG? Which tools have side effects, and are they gated?",
  "What does the real workload look like: prompt lengths, prefix reuse, concurrency?",
  "Which evals should this app have, and which already exist?",
  "Where is serving slow, and which optimization would help without hurting quality?",
];

const STAGES = [
  {
    name: "Scan",
    price: "Free",
    body: "Reconstructs the application from code, docs, screenshots, traces and endpoints. Every finding cites its evidence and confidence; conflicts between README and code are shown, not hidden.",
    output: "Reliability + Inference Blueprint",
  },
  {
    name: "Forge",
    price: "$15 once",
    body: "Opens a draft pull request that installs only what the Blueprint justified: deterministic checks, targeted judges, tracing, workload configs and a CI gate. Each change states its reason and risk.",
    output: "Draft PR or patch",
  },
  {
    name: "Guard",
    price: "$25, then $10/mo",
    body: "Runs only the quality evals and serving benchmarks a change can affect. On a regression it writes the failing test first, localizes the cause, and validates a fix in a sandbox before proposing it.",
    output: "Checks + verified draft repairs",
  },
];

export default function Landing() {
  return (
    <div className="flex min-h-full flex-col">
      <AppHeader />

      <main className="flex-1">
        <section className="mx-auto grid w-full max-w-[1200px] gap-12 px-4 pt-20 pb-24 sm:px-6 lg:grid-cols-12 lg:pt-28">
          <div className="lg:col-span-7">
            <p className="num text-[12px] tracking-wide text-ember">INFERENCE RELIABILITY RETROFIT</p>
            <h1 className="mt-5 font-display text-[40px] leading-[1.05] font-semibold tracking-[-0.02em] text-fg-0 sm:text-[56px]">
              Make your LLM faster
              <br />
              without breaking it.
            </h1>
            <p className="mt-6 max-w-[560px] text-[16px] leading-relaxed text-fg-1">
              Connect an existing AI application. Furnace reconstructs its workload, installs the
              reliability layer, optimizes serving, and prevents quality or performance
              regressions.
            </p>
            <div className="mt-10">
              <EvidenceInput />
            </div>
          </div>

          <aside className="lg:col-span-5 lg:pt-14">
            <div className="border-l border-line pl-6">
              <p className="text-[12px] text-fg-3">A scan answers, with evidence</p>
              <ol className="mt-4 space-y-3">
                {QUESTIONS.map((q, i) => (
                  <li key={q} className="flex gap-3 text-[14px] leading-snug text-fg-1">
                    <span className="num pt-px text-[12px] text-fg-3">{String(i + 1).padStart(2, "0")}</span>
                    {q}
                  </li>
                ))}
              </ol>
            </div>
          </aside>
        </section>

        <section id="how" className="border-t border-line bg-bg-1">
          <div className="mx-auto grid w-full max-w-[1200px] px-4 sm:px-6 md:grid-cols-3">
            {STAGES.map((s, i) => (
              <div
                key={s.name}
                className={`py-12 md:px-8 ${i === 0 ? "md:pl-0" : "border-t border-line md:border-t-0 md:border-l"}`}
              >
                <div className="flex items-baseline justify-between">
                  <h2 className="font-display text-[20px] font-semibold tracking-[-0.01em]">{s.name}</h2>
                  <span className="num text-[12px] text-fg-2">{s.price}</span>
                </div>
                <p className="mt-4 text-[14px] leading-relaxed text-fg-1">{s.body}</p>
                <p className="num mt-6 text-[12px] text-fg-3">→ {s.output}</p>
              </div>
            ))}
          </div>
        </section>

        <BenchStrip />

        <section className="border-t border-line">
          <div className="mx-auto grid w-full max-w-[1200px] gap-8 px-4 py-16 sm:px-6 md:grid-cols-3">
            {[
              ["Failing test first", "No repair is proposed until Furnace has a test that fails on the regression and passes on the base commit."],
              ["Human merge", "Every change arrives as a draft pull request. Furnace never pushes to a default branch or touches production."],
              ["Your keys, your GPUs", "Evals and benchmarks run on your endpoints and your model keys. Source is treated as data, never as instructions."],
            ].map(([t, b]) => (
              <div key={t}>
                <h3 className="text-[14px] font-medium text-fg-0">{t}</h3>
                <p className="mt-2 text-[13px] leading-relaxed text-fg-2">{b}</p>
              </div>
            ))}
          </div>
        </section>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex h-14 w-full max-w-[1200px] items-center justify-between px-4 text-[12px] text-fg-3 sm:px-6">
          <span>Furnace · beta</span>
          <span className="num">v0.1</span>
        </div>
      </footer>
    </div>
  );
}
