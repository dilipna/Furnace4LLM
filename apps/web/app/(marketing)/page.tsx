import Link from "next/link";
import { BenchStrip } from "@/components/marketing/bench-strip";
import { PrReview } from "@/components/marketing/pr-review";
import { AppHeader } from "@/components/ui/app-header";
import { SiteFooter } from "@/components/ui/site-footer";

// Figures are read from bench/results per request, never frozen at build time.
export const dynamic = "force-dynamic";

const GAPS = [
  {
    tool: "Output-quality evals in CI",
    examples: [
      ["promptfoo", "https://promptfoo.dev/docs/integrations/github-action"],
      ["Braintrust", "https://www.braintrust.dev/docs/evaluate/run-in-ci"],
      ["LangSmith", "https://docs.langchain.com/langsmith/pytest"],
    ],
    does: "Score the model's answers on each pull request against your datasets and thresholds.",
    leaves: "Serving latency and prompt-cache reuse on your own model server. In the run above, the answers did not change.",
  },
  {
    tool: "Code benchmarks in CI",
    examples: [["CodSpeed", "https://codspeed.io/docs"]],
    does: "Measure Python functions on every pull request with stable CPU instrumentation.",
    leaves: "Time spent inside the GPU model server, which is where this regression happens.",
  },
  {
    tool: "Production monitoring",
    examples: [],
    does: "Shows latency, cost and cache hit rates once traffic arrives.",
    leaves: "Catching the change before merge, and finding the line that caused it.",
  },
];

const FLOW: { step: string; body: string; status: "verified" | "mock" }[] = [
  { step: "Connect", body: "Install a GitHub App on one repository. Each job gets a token scoped to that repository and only the permissions it needs.", status: "mock" },
  { step: "Baseline", body: "Render main's real prompts with your app's own code, then measure them on your endpoint. Furnace never uses synthetic text.", status: "verified" },
  { step: "Inspect", body: "Map each changed line to the prompts, models and serving settings it affects, and run only the checks that can change.", status: "verified" },
  { step: "Gate", body: "Run main and the PR in interleaved runs, then compare time to first token with a 90% interval. The result is PASS, BLOCK or INCONCLUSIVE.", status: "verified" },
  { step: "Repair", body: "For a supported regression, write a failing test first, try rule-based fixes in order, and keep the first one that passes the tests and the gate.", status: "verified" },
  { step: "Review", body: "Open the fix as a draft pull request with its evidence attached. A person decides; Furnace never merges.", status: "mock" },
];

const SUPPORTED = [
  "Python applications that build prompts in code",
  "An OpenAI-compatible endpoint you serve (measured on vLLM)",
  "A machine with Docker and a GPU for the runner",
  "Repair of one regression family: per-request values at the start of the prompt",
];
const NOT_YET = [
  "TypeScript or other languages (configs and docs are still read)",
  "Latency on hosted APIs such as OpenAI or Anthropic: not measured yet",
  "Repairs for other regressions: refused with a reason, never guessed",
  "Pull requests from forks, whose code would run on your runner",
];

export default function Landing() {
  return (
    <div className="flex min-h-full flex-col">
      <AppHeader />

      <main className="flex-1">
        <section className="relative overflow-hidden">
          <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-ember/50 to-transparent" />
          <div className="mx-auto grid w-full max-w-[1200px] gap-12 px-4 pt-14 pb-20 sm:px-6 lg:grid-cols-12 lg:gap-14 lg:pt-20">
            <div className="lg:col-span-5 lg:pt-4">
              <p className="num text-[11.5px] tracking-[0.08em] text-ember uppercase">Performance checks for Python LLM apps</p>
              <h1 className="mt-5 font-display text-[38px] leading-[1.04] font-semibold tracking-[-0.025em] text-fg-0 sm:text-[52px]">
                Catch the pull request that makes your LLM app slow.
              </h1>
              <p className="mt-6 text-[16px] leading-relaxed text-fg-1">
                Furnace benchmarks each pull request on your own model server. It blocks changes that break prompt
                caching or raise time to first token, and drafts a fix it has already tested. Your team reviews and
                merges.
              </p>
              <p className="mt-4 text-[14px] leading-relaxed text-fg-2">
                Built for small teams that serve their own models with vLLM. For them, one harmless-looking prompt edit
                can multiply latency and GPU cost without failing a single test.
              </p>
              <div className="mt-8 flex flex-wrap items-center gap-3">
                <Link
                  href="/pilot"
                  className="inline-flex h-10 items-center rounded-[3px] bg-ember px-5 text-[14px] font-medium text-bg-0 transition-colors duration-150 hover:bg-ember-hi"
                >
                  Set up a pilot
                </Link>
                <Link
                  href="/guard/r1_dynamic_head"
                  className="inline-flex h-10 items-center rounded-[3px] border border-line-strong px-5 text-[14px] text-fg-0 transition-colors duration-150 hover:border-fg-3 hover:bg-bg-2"
                >
                  Inspect the full recorded run
                </Link>
              </div>
              <ul className="num mt-8 space-y-1.5 text-[12px] text-fg-3">
                <li>Python · OpenAI-compatible endpoint (measured on vLLM)</li>
                <li>Runner on your GPU machine · your code stays on it</li>
                <li>GitHub check runs and draft pull requests</li>
              </ul>
            </div>
            <div className="lg:col-span-7">
              <PrReview />
            </div>
          </div>
        </section>

        <section id="why" aria-labelledby="why-h" className="border-t border-line bg-bg-1">
          <div className="mx-auto w-full max-w-[1200px] px-4 py-16 sm:px-6">
            <p className="num text-[11.5px] tracking-[0.08em] text-ember uppercase">Why it slips through</p>
            <h2 id="why-h" className="mt-3 max-w-[760px] font-display text-[28px] leading-tight font-semibold tracking-[-0.015em]">
              Every existing check passes. Latency still goes up, and you find out from your users.
            </h2>
            <p className="mt-4 max-w-[720px] text-[14px] leading-relaxed text-fg-2">
              Model servers such as vLLM reuse work across requests that begin with the same text. Put a request id, a
              timestamp or a user name at the top of the prompt, and that reuse is gone. The answers do not change, so
              the tests that look at answers stay green.
            </p>
            <div className="mt-10 overflow-x-auto">
              <table className="w-full min-w-[720px] border-collapse text-left text-[13px]">
                <thead>
                  <tr className="border-b border-line-strong text-[11.5px] tracking-wide text-fg-3 uppercase">
                    <th className="py-3 pr-6 font-normal">What teams use today</th>
                    <th className="py-3 pr-6 font-normal">What it does well</th>
                    <th className="py-3 font-normal">What it leaves to you</th>
                  </tr>
                </thead>
                <tbody>
                  {GAPS.map((g) => (
                    <tr key={g.tool} className="border-b border-line align-top">
                      <td className="py-4 pr-6">
                        <div className="text-fg-0">{g.tool}</div>
                        {g.examples.length > 0 && (
                          <div className="mt-1 text-[12px] text-fg-3">
                            e.g.{" "}
                            {g.examples.map(([n, u], j) => (
                              <span key={n}>
                                <a href={u} className="underline decoration-line-strong underline-offset-2 hover:text-fg-1">
                                  {n}
                                </a>
                                {j < g.examples.length - 1 ? ", " : ""}
                              </span>
                            ))}
                          </div>
                        )}
                      </td>
                      <td className="py-4 pr-6 text-fg-1">{g.does}</td>
                      <td className="py-4 text-fg-1">{g.leaves}</td>
                    </tr>
                  ))}
                  <tr className="align-top">
                    <td className="py-4 pr-6 font-medium text-ember">Furnace</td>
                    <td className="py-4 pr-6 text-fg-0">
                      Measures the PR’s own prompts on your server before merge, decides with an interval, and drafts a
                      tested fix for one supported regression family.
                    </td>
                    <td className="py-4 text-fg-1">Answer quality: keep your eval tool for that. Furnace sits beside it.</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-[11px] text-fg-3">Other tools are described from their public documentation (October 2026).</p>
          </div>
        </section>

        <section id="how" aria-labelledby="how-h" className="border-t border-line">
          <div className="mx-auto w-full max-w-[1200px] px-4 py-16 sm:px-6">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <p className="num text-[11.5px] tracking-[0.08em] text-ember uppercase">How it works</p>
                <h2 id="how-h" className="mt-3 font-display text-[28px] font-semibold tracking-[-0.015em]">
                  From connected repository to a reviewed fix
                </h2>
              </div>
              <p className="flex flex-wrap items-center gap-4 text-[12px] text-fg-3">
                <span className="inline-flex items-center gap-1.5">
                  <span aria-hidden="true" className="h-2 w-2 rounded-full bg-ok" /> verified on the fixture apps
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span aria-hidden="true" className="h-2 w-2 rounded-full border border-dashed border-fg-2" /> tested against a mock GitHub only
                </span>
              </p>
            </div>
            <div className="ticks mt-8" aria-hidden="true" />
            <ol className="grid gap-px border border-line bg-line sm:grid-cols-2 lg:grid-cols-3">
              {FLOW.map((f, i) => (
                <li key={f.step} className="bg-bg-0 p-6">
                  <div className="flex items-center justify-between">
                    <span className="num text-[12px] text-fg-3">{String(i + 1).padStart(2, "0")}</span>
                    <span
                      role="img"
                      aria-label={f.status === "verified" ? "verified on the fixture apps" : "tested against a mock GitHub only"}
                      className={`h-2 w-2 rounded-full ${f.status === "verified" ? "bg-ok" : "border border-dashed border-fg-2"}`}
                    />
                  </div>
                  <h3 className="mt-4 font-display text-[18px] font-semibold">{f.step}</h3>
                  <p className="mt-2 text-[13px] leading-relaxed text-fg-2">{f.body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <BenchStrip />

        <section aria-labelledby="scope-h" className="border-t border-line bg-bg-1">
          <div className="mx-auto grid w-full max-w-[1200px] gap-10 px-4 py-16 sm:px-6 md:grid-cols-2">
            <div>
              <h2 id="scope-h" className="font-display text-[20px] font-semibold">Works today</h2>
              <ul className="mt-5 space-y-3 text-[14px] text-fg-1">
                {SUPPORTED.map((s) => (
                  <li key={s} className="flex gap-3">
                    <span aria-hidden="true" className="text-ok">✓</span>
                    {s}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h2 className="font-display text-[20px] font-semibold">Not yet</h2>
              <ul className="mt-5 space-y-3 text-[14px] text-fg-2">
                {NOT_YET.map((s) => (
                  <li key={s} className="flex gap-3">
                    <span aria-hidden="true" className="text-fg-3">○</span>
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        <section aria-labelledby="pilot-h" className="border-t border-line">
          <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-6 px-4 py-16 sm:px-6 md:flex-row md:items-center md:justify-between">
            <div className="max-w-[640px]">
              <h2 id="pilot-h" className="font-display text-[28px] font-semibold tracking-[-0.015em]">
                Looking for design partners
              </h2>
              <p className="mt-3 text-[14px] leading-relaxed text-fg-2">
                If you serve a Python LLM app on your own GPUs, we will set Furnace up with you on one repository in a
                single working session. You keep the setup and the results. In return, we ask for an honest account of
                what was useful and what was not.
              </p>
            </div>
            <Link
              href="/pilot"
              className="inline-flex h-10 shrink-0 items-center self-start rounded-[3px] bg-ember px-5 text-[14px] font-medium text-bg-0 transition-colors duration-150 hover:bg-ember-hi md:self-auto"
            >
              See what a pilot involves
            </Link>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}
