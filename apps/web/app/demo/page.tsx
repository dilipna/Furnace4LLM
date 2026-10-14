import type { Metadata } from "next";
import Link from "next/link";
import { BenchStrip } from "@/components/marketing/bench-strip";
import { LiveGithub } from "@/components/marketing/live-github";
import { PrReview } from "@/components/marketing/pr-review";
import { AppHeader } from "@/components/ui/app-header";
import { SiteFooter } from "@/components/ui/site-footer";
import { RECORDED_ONLY } from "@/lib/site";

export const metadata: Metadata = {
  title: "Demo · Furnace",
  description: "One pull request through Furnace, recorded: the change, its measured effect, the decision and a tested fix.",
};

// Figures are read from bench/results per request.
export const dynamic = "force-dynamic";

// Served from apps/web/public/demo/ (published with the site), or a URL set at build time.
const DEFAULT_VIDEO = "/demo/furnace-demo.webm";
const VIDEO = process.env.NEXT_PUBLIC_DEMO_VIDEO ?? DEFAULT_VIDEO;

export default function DemoPage() {
  return (
    <div className="flex min-h-full flex-col">
      <AppHeader variant="marketing" active="/demo" />
      <main className="flex-1">
        <section className="mx-auto w-full max-w-[1100px] px-4 pt-16 pb-10 sm:px-6">
          <p className="num text-[11.5px] tracking-[0.1em] text-ember uppercase">Demo · recorded</p>
          <h1 className="mt-4 max-w-[760px] font-display text-[36px] leading-[1.06] font-semibold tracking-[-0.03em] sm:text-[52px]">
            One pull request, start to finish.
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

        <section aria-labelledby="video-h" className="mx-auto w-full max-w-[1100px] px-4 pb-16 sm:px-6">
          <h2 id="video-h" className="sr-only">
            Screen recording
          </h2>
          <div className="overflow-hidden rounded-[10px] border border-line-strong bg-bg-1">
            <video controls preload="metadata" playsInline poster="/demo/poster.png" className="aspect-video w-full bg-bg-0">
              <source src={VIDEO} type={VIDEO.endsWith(".mp4") ? "video/mp4" : "video/webm"} />
              {/* H.264 copy of the same recording for browsers without WebM (older iPhones) */}
              {VIDEO === DEFAULT_VIDEO && <source src="/demo/furnace-demo.mp4" type="video/mp4" />}
              Your browser cannot play this recording.{" "}
              <a href="/demo/furnace-demo.mp4" className="underline">
                Download it (MP4)
              </a>
              .
            </video>
            <p className="border-t border-line px-4 py-2.5 text-[11.5px] text-fg-3">
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
              <PrReview />
            </div>
          </div>
        </section>

        <LiveGithub />

        <BenchStrip />
      </main>
      <SiteFooter />
    </div>
  );
}
