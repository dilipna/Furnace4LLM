import Link from "next/link";
import { Faq } from "@/components/marketing/faq";
import { HeroCard } from "@/components/marketing/hero-card";
import { Steps } from "@/components/marketing/steps";
import { AppHeader } from "@/components/ui/app-header";
import { SiteFooter } from "@/components/ui/site-footer";
import { loadStory } from "@/lib/story";
import { dynamicUnlessRecorded } from "@/lib/render";

const WORKS_WITH = ["Python", "vLLM", "OpenAI-compatible APIs", "GitHub", "Docker"];

function Cta({ href, children, primary }: { href: string; children: React.ReactNode; primary?: boolean }) {
  return (
    <Link
      href={href}
      className={`inline-flex h-11 items-center rounded-full px-6 text-[14px] font-medium transition-colors duration-150 ${
        primary ? "bg-ember text-bg-0 hover:bg-ember-hi" : "border border-line-strong text-fg-0 hover:border-fg-3 hover:bg-bg-2"
      }`}
    >
      {children}
    </Link>
  );
}

export default async function Landing() {
  await dynamicUnlessRecorded();
  const s = await loadStory();
  const slower = s ? Math.round(s.pr / s.base) : null;
  const stepData = {
    prChange: s?.prChange ?? null,
    prCi: s?.prCi ?? null,
    repairVsMain: s?.repairVsMain[0] ?? null,
    repairUpper: s?.repairVsMainUpper[0] ?? null,
    repairLower: s?.repairVsMainLower[0] ?? null,
    repairVsPr: s?.repairVsPr[0] ?? null,
    verified: s?.verified ?? 0,
    trials: s?.trials ?? 0,
  };
  const g = s?.gate;
  const stats = [
    g && [`${g.falseAlarms}/${g.n}`, "false alarms on unchanged code"],
    g && [`${g.blocks}/${g.blockN}`, "cache regressions blocked"],
    s && [`${s.verified}/${s.trials}`, "fixes verified, one scenario repeated"],
    g && [`${g.undecided}/${g.gradedN}`, "small slowdowns left undecided"],
  ].filter(Boolean) as [string, string][];

  return (
    <div className="flex min-h-full flex-col">
      <AppHeader variant="marketing" />

      <main className="flex-1">
        {/* Hero */}
        <section className="relative overflow-hidden">
          <div aria-hidden="true" className="hero-grid pointer-events-none absolute inset-0" />
          <div aria-hidden="true" className="hero-heat pointer-events-none absolute inset-x-0 bottom-0 h-[520px]" />
          <div className="relative mx-auto w-full max-w-[1100px] px-4 pt-16 pb-20 text-center sm:px-6 sm:pt-24">
            <Link
              href="/pilot"
              className="inline-flex items-center gap-2 rounded-full border border-line-strong bg-bg-1/80 px-3.5 py-1.5 text-[12.5px] text-fg-1 hover:border-fg-3"
            >
              <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-ember" />
              Early access: looking for design partners
              <span aria-hidden="true" className="text-fg-3">
                →
              </span>
            </Link>
            <h1 className="mx-auto mt-7 max-w-[900px] font-display text-[42px] leading-[1.02] font-semibold tracking-[-0.035em] text-fg-0 sm:text-[68px]">
              Ship prompt changes without slowing down your AI.
            </h1>
            <p className="mx-auto mt-6 max-w-[620px] text-[17px] leading-relaxed text-fg-1">
              Furnace tests every pull request on your own model server, blocks the ones that make responses slower, and
              drafts a tested fix. Your team just reviews it.
            </p>
            <div className="mt-9 flex flex-wrap justify-center gap-3">
              <Cta href="/pilot" primary>
                Become a design partner
              </Cta>
              <Cta href="/demo">See it catch one</Cta>
            </div>
            <p className="mt-5 text-[12.5px] text-fg-3">
              Shown end to end on a public GitHub repository:{" "}
              <Link href="/demo#gh-h" className="underline decoration-line-strong underline-offset-2 hover:text-fg-1">
                the check run and the draft fix
              </Link>
            </p>
            <div className="mt-12">
              <HeroCard s={s} />
            </div>
          </div>
        </section>

        {/* Works with */}
        <section aria-label="Works with" className="border-y border-line bg-bg-1/60">
          <div className="mx-auto flex w-full max-w-[1100px] flex-wrap items-center justify-center gap-x-10 gap-y-3 px-4 py-6 sm:px-6">
            <span className="text-[11.5px] tracking-[0.08em] text-fg-3 uppercase">Works with</span>
            {WORKS_WITH.map((w) => (
              <span key={w} className="num text-[14px] text-fg-2">
                {w}
              </span>
            ))}
          </div>
        </section>

        {/* Problem */}
        <section className="mx-auto w-full max-w-[1100px] px-4 py-24 text-center sm:px-6">
          <p className="num text-[11.5px] tracking-[0.1em] text-ember uppercase">The problem</p>
          <h2 className="mx-auto mt-4 max-w-[760px] font-display text-[34px] leading-[1.08] font-semibold tracking-[-0.025em] sm:text-[48px]">
            One small change. {slower ? `${slower}× slower.` : "Much slower."}
          </h2>
          <p className="mx-auto mt-5 max-w-[620px] text-[16px] leading-relaxed text-fg-2">
            A request ID added to the top of a prompt. The answers didn’t change, so every answer check passed. But the
            model server could no longer reuse its cached work, so every request waited longer.
          </p>
          {s && (
            <div className="mx-auto mt-14 grid max-w-[760px] gap-px overflow-hidden rounded-[10px] border border-line bg-line sm:grid-cols-2">
              <div className="bg-bg-0 px-6 py-8">
                <p className="font-display text-[44px] font-semibold tracking-[-0.03em] text-fg-0">
                  {s.hitBase != null ? Math.round(s.hitBase * 100) : "–"}% <span className="text-fg-3">→</span>{" "}
                  <span className="text-ember">{s.hitPr != null ? Math.round(s.hitPr * 100) : "–"}%</span>
                </p>
                <p className="mt-1 text-[14px] text-fg-2">of the prompt reused from the server’s cache</p>
              </div>
              <div className="bg-bg-0 px-6 py-8">
                <p className="font-display text-[44px] font-semibold tracking-[-0.03em] text-fg-0">
                  {s.base.toFixed(0)} <span className="text-fg-3">→</span> <span className="text-ember">{s.pr.toFixed(0)}</span>
                  <span className="text-[22px] text-fg-2"> ms</span>
                </p>
                <p className="mt-1 text-[14px] text-fg-2">time to first token (geometric mean)</p>
              </div>
            </div>
          )}
          {s && (
            <p className="mt-4 text-[11.5px] text-fg-3">
              Recorded on a fixture app, laptop RTX 3050 Ti, vLLM, Qwen2.5-0.5B (trial 1 of {s.trials}).
            </p>
          )}
        </section>

        {/* How it works */}
        <section id="how" className="border-t border-line bg-bg-1/40">
          <div className="mx-auto w-full max-w-[1100px] px-4 py-24 sm:px-6">
            <p className="num text-[11.5px] tracking-[0.1em] text-ember uppercase">How it works</p>
            <h2 className="mt-4 max-w-[640px] font-display text-[34px] leading-[1.08] font-semibold tracking-[-0.025em] sm:text-[44px]">
              A performance check for every pull request.
            </h2>
            <div className="mt-14">
              <Steps d={stepData} />
            </div>
          </div>
        </section>

        {/* Evidence */}
        {stats.length > 0 && (
          <section className="border-t border-line">
            <div className="mx-auto w-full max-w-[1100px] px-4 py-24 sm:px-6">
              <div className="flex flex-wrap items-end justify-between gap-6">
                <div>
                  <p className="num text-[11.5px] tracking-[0.1em] text-ember uppercase">Evidence</p>
                  <h2 className="mt-4 max-w-[620px] font-display text-[34px] leading-[1.08] font-semibold tracking-[-0.025em] sm:text-[44px]">
                    Measured, including the misses.
                  </h2>
                </div>
                <Link href="/bench" className="text-[14px] text-fg-2 hover:text-fg-0">
                  Every result and correction →
                </Link>
              </div>
              <div className="mt-14 grid gap-px overflow-hidden rounded-[10px] border border-line bg-line sm:grid-cols-2 lg:grid-cols-4">
                {stats.map(([v, l], j) => (
                  <div key={l} className="bg-bg-0 px-6 py-8">
                    <p className={`font-display text-[44px] font-semibold tracking-[-0.03em] ${j === stats.length - 1 && g ? "text-fg-2" : "text-fg-0"}`}>{v}</p>
                    <p className="mt-1 text-[14px] text-fg-2">{l}</p>
                  </div>
                ))}
              </div>
              <p className="mt-4 max-w-[760px] text-[12px] leading-relaxed text-fg-3">
                Two fixture apps, one laptop GPU, one small model. Every figure is read from a result file in the repository.
                The GitHub flow (check run, draft fix, independent verification) was shown once on a public repository; see the Demo page.
              </p>
            </div>
          </section>
        )}

        {/* FAQ */}
        <section id="faq" className="border-t border-line">
          <div className="mx-auto grid w-full max-w-[1100px] gap-10 px-4 py-24 sm:px-6 lg:grid-cols-12">
            <div className="lg:col-span-4">
              <p className="num text-[11.5px] tracking-[0.1em] text-ember uppercase">FAQ</p>
              <h2 className="mt-4 font-display text-[34px] leading-[1.08] font-semibold tracking-[-0.025em]">Straight answers.</h2>
            </div>
            <div className="lg:col-span-8">
              <Faq s={s} />
            </div>
          </div>
        </section>

        {/* Final CTA */}
        <section className="relative overflow-hidden border-t border-line">
          <div aria-hidden="true" className="hero-heat pointer-events-none absolute inset-x-0 bottom-0 h-[360px]" />
          <div className="relative mx-auto w-full max-w-[1100px] px-4 py-28 text-center sm:px-6">
            <h2 className="mx-auto max-w-[760px] font-display text-[36px] leading-[1.06] font-semibold tracking-[-0.03em] sm:text-[52px]">
              Serve your own models? Let’s test one repository together.
            </h2>
            <p className="mx-auto mt-5 max-w-[520px] text-[16px] text-fg-2">
              A free pilot, set up with you in one session. You keep everything it finds.
            </p>
            <div className="mt-9 flex flex-wrap justify-center gap-3">
              <Cta href="/pilot" primary>
                Become a design partner
              </Cta>
              <Cta href="/demo">See it catch one</Cta>
            </div>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}
