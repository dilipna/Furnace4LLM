import Link from "next/link";
import type { Story } from "@/lib/story";

const pct = (x: number) => `${x > 0 ? "+" : ""}${x.toFixed(0)}%`;
const hit = (h: number | null) => (h == null ? "–" : `${Math.round(h * 100)}%`);

/** The hero's product visual: one pull request as a check run, abstracted to its decision. */
export function HeroCard({ s }: { s: Story | null }) {
  if (!s) {
    return (
      <div className="mx-auto w-full max-w-[640px] rounded-[10px] border border-dashed border-line-strong bg-bg-1/80 p-8 text-center text-[13px] text-fg-2">
        The recorded run could not be loaded because the results API did not answer.{" "}
        <Link href="/demo" className="underline underline-offset-2">
          Try the demo page
        </Link>
        .
      </div>
    );
  }
  const max = Math.max(s.pr, s.base, s.repair ?? 0);
  return (
    <figure className="relative mx-auto w-full max-w-[640px] overflow-hidden rounded-[10px] border border-line-strong bg-bg-1/90 text-left shadow-[0_30px_80px_-30px_rgba(242,106,27,0.35)] backdrop-blur">
      <figcaption className="flex items-center justify-between border-b border-line px-5 py-3">
        <span className="flex items-center gap-2 text-[12px] text-fg-1">
          <span aria-hidden="true" className="h-3.5 w-3.5 rounded-[3px] border border-line-strong bg-bg-0 p-[3px]">
            <span className="block h-full w-full rounded-[1px] bg-ember" />
          </span>
          Furnace Guard · check run
        </span>
        <span className="num rounded-full border border-line-strong px-2 py-0.5 text-[10.5px] tracking-wide text-fg-2">RECORDED RUN</span>
      </figcaption>
      <div className="px-5 pt-4 pb-5">
        <p className="text-[11.5px] text-fg-3">Pull request · fixture support app</p>
        <p className="mt-1 text-[15px] font-medium text-fg-0">Add request id and timestamp to the system prompt</p>

        <div className="mt-5 space-y-2.5">
          <p className="text-[11.5px] text-fg-3">Time to first token on the model server</p>
          {[
            ["main", s.base, "bg-fg-3", hit(s.hitBase)],
            ["this PR", s.pr, "bg-ember", hit(s.hitPr)],
          ].map(([label, ms, color, h]) => (
            <div key={label as string} className="grid grid-cols-[58px_1fr_auto] items-center gap-3">
              <span className="text-[12px] text-fg-1">{label}</span>
              <div className="h-2 rounded-full bg-bg-3">
                <div className={`bar-fill h-full rounded-full ${color}`} style={{ width: `${Math.max(2, ((ms as number) / max) * 100)}%` }} />
              </div>
              <span className="num w-[132px] text-right text-[12px] text-fg-0">
                {(ms as number).toFixed(0)} ms <span className="text-fg-3">· cache {h}</span>
              </span>
            </div>
          ))}
        </div>

        <div className="mt-5 grid grid-cols-1 gap-2 sm:grid-cols-2">
          <div className="flex items-center gap-3 rounded-[6px] border border-bad/40 bg-bad/10 px-3 py-2.5">
            <span aria-hidden="true" className="text-bad">
              ✕
            </span>
            <div>
              <p className="text-[12.5px] font-medium text-fg-0">Blocked before merge</p>
              <p className="num text-[11px] text-fg-2">
                {pct(s.prChange)}
                {s.prCi ? `, 90% interval ${pct(s.prCi[0])} to ${pct(s.prCi[1])}` : ""}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3 rounded-[6px] border border-ok/40 bg-ok/10 px-3 py-2.5">
            <span aria-hidden="true" className="text-ok">
              ✓
            </span>
            <div>
              <p className="text-[12.5px] font-medium text-fg-0">Fix drafted and tested</p>
              <p className="num text-[11px] text-fg-2">
                {s.repair != null ? `${s.repair.toFixed(0)} ms · cache ${hit(s.hitRepair)} · awaiting review` : "not verified in this trial"}
              </p>
            </div>
          </div>
        </div>
      </div>
      <p className="border-t border-line px-5 py-2.5 text-[10.5px] leading-relaxed text-fg-3">
        Trial 1 of {s.trials} repeated trials of one scenario, laptop RTX 3050 Ti, vLLM, Qwen2.5-0.5B.{" "}
        <Link href="/demo" className="underline decoration-line-strong underline-offset-2 hover:text-fg-1">
          Full walkthrough
        </Link>
      </p>
    </figure>
  );
}
