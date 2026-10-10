import Link from "next/link";
import { type Agg, campaigns, getRq, type Rq3, type Rq4, type Rq5 } from "@/lib/bench";

type Micro = Record<string, { tp: number; n_truth: number } | undefined>;
type Rq1 = { micro: Record<string, Micro> };

/** Headline FurnaceBench numbers for the landing page. Renders nothing unless results exist. */
export async function BenchStrip() {
  let list;
  try {
    list = await campaigns();
  } catch {
    return null; // API down: the landing page must still render
  }
  const latest = (rq: string) => list.find((c) => c.available.includes(rq))?.name;
  const [c1, c3, c4, c5] = [latest("rq1"), latest("rq3"), latest("rq4"), latest("rq5")];
  const [rq1, rq3, rq4, rq5] = await Promise.all([
    c1 ? getRq<Rq1>(c1, "rq1").catch(() => null) : null,
    c3 ? getRq<Rq3>(c3, "rq3").catch(() => null) : null,
    c4 ? getRq<Rq4>(c4, "rq4").catch(() => null) : null,
    c5 ? getRq<Rq5>(c5, "rq5").catch(() => null) : null,
  ]);

  const tiles: { label: string; value: string; note: string }[] = [];
  // the newest held-out set: labeled before the scanner change it measures
  const hoSplit = rq1?.micro["held-out-3"]?.llm_call_sites?.n_truth ? "held-out-3" : "held-out-2";
  const ho = rq1?.micro[hoSplit]?.llm_call_sites;
  if (ho && ho.n_truth) {
    tiles.push({ label: "LLM call sites found on held-out apps", value: `${ho.tp}/${ho.n_truth}`, note: `RQ1 ${hoSplit === "held-out-3" ? "set 3" : "set 2"}: apps labeled before the scanner saw them; misses are listed on /bench` });
  }
  if (rq3) {
    const r = rq3.summary.regression_recall;
    tiles.push({
      label: "regressions caught while running a fraction of the suite",
      value: `${r.caught}/${r.total}`,
      note: `RQ3, ${rq3.summary.items_executed_pct.toFixed(0)}% of checks executed on ${rq3.summary.scenarios} PRs`,
    });
  }
  const eff = rq4?.prefix_effect.find((e) => e.max_num_seqs === 32 && e.level === 16);
  const m = (a: Agg | undefined) => a?.median;
  if (eff && m(eff.ttft_p95_off_vs_on_pct) != null) {
    tiles.push({
      label: "p95 TTFT when prefix caching is off (c=16, max-num-seqs 32)",
      value: `${(m(eff.ttft_p95_off_vs_on_pct) as number) > 0 ? "+" : ""}${(m(eff.ttft_p95_off_vs_on_pct) as number).toFixed(0)}%`,
      note: `RQ4, real F1 workload on a laptop RTX 3050 Ti, ${eff.n_pairs} paired repeats`,
    });
  }
  const r1 = rq5?.attempts.filter((a) => a.scenario === "r1_dynamic_head") ?? [];
  if (r1.length) {
    tiles.push({
      label: "prompt-cache regression repairs verified",
      value: `${r1.filter((a) => a.status === "verified").length}/${r1.length}`,
      note: "RQ5, failing test first, sandbox-validated, full-suite audit",
    });
  }
  if (!tiles.length) return null;

  return (
    <section className="border-t border-line" aria-labelledby="bench-strip">
      <div className="mx-auto w-full max-w-[1200px] px-4 py-14 sm:px-6">
        <div className="flex flex-wrap items-baseline justify-between gap-4">
          <h2 id="bench-strip" className="font-display text-[20px] font-semibold tracking-[-0.01em]">
            Measured, with the misses
          </h2>
          <Link href="/bench" className="text-[13px] text-fg-2 hover:text-fg-0">
            Full FurnaceBench report →
          </Link>
        </div>
        <div className="mt-8 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          {tiles.map((t) => (
            <div key={t.label} className="border-l border-line pl-4">
              <div className="font-display text-[32px] font-semibold tracking-[-0.02em] text-fg-0">{t.value}</div>
              <div className="mt-1 text-[13px] text-fg-1">{t.label}</div>
              <div className="mt-1 text-[11px] text-fg-3">{t.note}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
