import type { Metadata } from "next";
import Link from "next/link";
import { BenchStrip } from "@/components/marketing/bench-strip";
import { LiveGithub } from "@/components/marketing/live-github";
import { OutcomeGuide } from "@/components/marketing/outcome-guide";
import { PrReview } from "@/components/marketing/pr-review";
import { AppHeader } from "@/components/ui/app-header";
import { SiteFooter } from "@/components/ui/site-footer";
import { dynamicUnlessRecorded } from "@/lib/render";
import { RECORDED_ONLY } from "@/lib/site";

export const metadata: Metadata = {
  title: "Demo · Furnace",
  description: "One pull request through Furnace, recorded: the change, its measured effect, the decision and a tested fix.",
};

// Served from apps/web/public/demo/ (published with the site), or a URL set at build time.
const DEFAULT_VIDEO = "/demo/furnace-demo.webm";
const VIDEO = process.env.NEXT_PUBLIC_DEMO_VIDEO ?? DEFAULT_VIDEO;

export default async function DemoPage() {
  await dynamicUnlessRecorded();
  return (
    <div className="flex min-h-full flex-col">
      <AppHeader variant="marketing" active="/demo" />
      <a href="#main" className="sr-only focus:not-sr-only focus:p-4">Skip to content</a>
      <main id="main" className="flex-1">
        <section className="mx-auto w-full max-w-[1100px] px-4 pt-16 pb-10 sm:px-6">
          <p className="num text-[11.5px] tracking-[0.1em] text-ember uppercase">Demo · recorded</p>
          <h1 className="mt-4 max-w-[760px] font-display text-[36px] leading-[1.06] font-semibold tracking-[-0.03em] sm:text-[52px]">
            A prompt edit made the app slower. Furnace caught it.
          </h1>
          <p className="mt-5 max-w-[640px] text-[16px] leading-relaxed text-fg-2">
            Everything on this page is a recording, not a live run. The numbers come from the stored results of three
            repeated trials.{" "}
            {RECORDED_ONLY ? (
              "Live runs happen on the owner’s runner; this site is not connected to one, so it shows recordings only."
            ) : (
              <>
                Live runs happen on the owner’s runner and are shown on the{" "}
                <Link href="/guard/r1_dynamic_head" className="underline decoration-line-strong underline-offset-2 hover:text-fg-0">
                  Guard page
                </Link>{" "}
                when it is connected.
              </>
            )}
          </p>
        </section>

        <section aria-labelledby="sequence-h" className="mx-auto w-full max-w-[1100px] px-4 pb-10 sm:px-6">
          <p className="max-w-[800px] text-base leading-relaxed text-fg-2">A pull request proposes a code change for review before it is merged. Here, a request ID and timestamp were added before a shared prompt. That changing beginning stopped the model server reusing its prefix cache: saved work for identical prompt beginnings. Users waited longer for the first response token (latency).</p>
          <h2 id="sequence-h" className="mt-8 font-display text-2xl font-semibold">The recorded result, without the video</h2>
          <ol className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-5" aria-label="Recorded evaluation sequence">
            {[
              ["Change", "A different ID starts every prompt, preventing reuse of the shared beginning."],
              ["Compare", "Furnace measures the original and proposed versions on the same model server."],
              ["Verdict", "The recorded slowdown crosses the blocking rule. The GitHub check fails."],
              ["Propose a fix", "A draft moves the ID to a log. Executed tests and measured repair checks pass; the answer-quality judge was skipped."],
              ["Human review", "Logging instead of sending the ID changes behavior. A person decides whether the draft is acceptable. Nothing is merged automatically."],
            ].map(([title, text], i) => <li key={title} className="rounded border border-line-strong p-4"><p className="num text-xs text-ember">{i + 1} →</p><h3 className="mt-2 font-semibold">{title}</h3><p className="mt-2 text-sm leading-relaxed text-fg-2">{text}</p></li>)}
          </ol>
          <p className="mt-5 text-sm text-fg-2">One fixture scenario, repeated three times on one laptop GPU. This does not establish answer equivalence, a general repair rate or performance on your app. <Link href="/pilot" className="underline">Check your app’s fit and first evaluation steps.</Link></p>
        </section>

        <section aria-labelledby="video-h" className="mx-auto w-full max-w-[1100px] px-4 pb-16 sm:px-6">
          <h2 id="video-h" className="sr-only">
            Screen recording
          </h2>
          <div className="overflow-hidden rounded-[10px] border border-line-strong bg-bg-1">
            <video aria-label="Recorded Furnace rehearsal, 14 October 2026; text explanation above and trial details below" controls preload="metadata" playsInline poster="/demo/poster.png" className="aspect-video w-full bg-bg-0">
              {/* H.264 copy first: every browser plays it, and WebKit (Safari) plays it where its WebM
                  support failed in testing; the original WebM stays as the fallback */}
              {VIDEO === DEFAULT_VIDEO && <source src="/demo/furnace-demo.mp4" type="video/mp4" />}
              <source src={VIDEO} type={VIDEO.endsWith(".mp4") ? "video/mp4" : "video/webm"} />
              Your browser cannot play this recording.{" "}
              <a href="/demo/furnace-demo.mp4" className="underline">
                Download it (MP4)
              </a>
              .
            </video>
            <p className="border-t border-line px-4 py-3 text-sm leading-relaxed text-fg-2">
              Silent screen recording of the end-to-end rehearsal, 2026-10-14, on a laptop: the landing and this page, a public GitHub scan, the graph, a live benchmark, and a live Guard run that flags the regression (about two minutes of it is the run itself). Narration follows the{" "}
              <a
                className="underline decoration-line-strong underline-offset-2 hover:text-fg-1"
                href="https://github.com/dilipna/Furnace4LLM/blob/main/docs/demo-3min.md"
              >
                three-minute script
              </a>
              .
            </p>
          </div>
        </section>

        <section aria-labelledby="walk-h" className="border-t border-line bg-bg-1/40">
          <div className="mx-auto grid w-full max-w-[1100px] gap-10 px-4 py-16 sm:px-6 lg:grid-cols-12">
            <div className="lg:col-span-4">
              <h2 id="walk-h" className="font-display text-[28px] leading-tight font-semibold tracking-[-0.02em]">
                The pull request, step by step
              </h2>
              <p className="mt-4 text-[14px] leading-relaxed text-fg-2">
                The exact change, the measured effect on the model server, the gate’s decision, the fix Furnace drafted, and
                the human review it waits for. Switch between the three trials; each one is compared inside its own
                interleaved runs.
              </p>
            </div>
            <div className="lg:col-span-8">
              <details className="rounded border border-line-strong p-4">
                <summary className="cursor-pointer font-medium">Inspect recorded diffs, trial measurements and exact decision</summary>
                <div className="mt-6"><PrReview /></div>
              </details>
            </div>
          </div>
        </section>

        <OutcomeGuide />
        <LiveGithub />

        <BenchStrip />
      </main>
      <SiteFooter />
    </div>
  );
}
