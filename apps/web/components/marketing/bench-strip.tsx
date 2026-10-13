import Link from "next/link";
import { type Agg, campaigns, getRq, type Rq3, type Rq4, type Rq5 } from "@/lib/bench";

type Micro = Record<string, { tp: number; n_truth: number } | undefined>;
type Rq1 = { micro: Record<string, Micro> };

/** The campaign holding held-out set 6's single first scan (docs/scanner-eval-set6.md). */
const HELD_OUT_FIRST_SCAN = "2026-10-13-set6";

/** Headline FurnaceBench numbers for the landing page. Renders nothing unless results exist. */
export async function BenchStrip() {
  let list;
  try {
    list = await campaigns();
  } catch {
    return null; // API down: the landing page must still render
  }
  const latest = (rq: string) => list.find((c) => c.available.includes(rq))?.name;
  const [c3, c4, c5] = [latest("rq3"), latest("rq4"), latest("rq5")];
  const [rq3, rq4, rq5] = await Promise.all([
    c3 ? getRq<Rq3>(c3, "rq3").catch(() => null) : null,
    c4 ? getRq<Rq4>(c4, "rq4").catch(() => null) : null,
    c5 ? getRq<Rq5>(c5, "rq5").catch(() => null) : null,
  ]);

  const tiles: { label: string; value: string; note: string }[] = [];
  // Only a FIRST scan of a held-out set is a held-out figure: once a set has been used to fix
  // the scanner, its score measures fit. Set 6 was scored once at the frozen scanner (41ca529);
  // that campaign is pinned here so a later rescan can never replace it on this tile.
  const set6 = await getRq<Rq1>(HELD_OUT_FIRST_SCAN, "rq1").catch(() => null);
  const ho = set6?.micro["held-out-6"]?.llm_call_sites;
  if (ho && ho.n_truth) {
    tiles.push({
      label: "LLM call sites found on apps the scanner had never seen",
      value: `${ho.tp}/${ho.n_truth}`,
      note: "RQ1 held-out set 6, first scan (scanner frozen at 41ca529, labels committed before it); misses are listed on /bench",
    });
  }
  if (rq3) {
    const r = rq3.summary.regression_recall;
    tiles.push({
      label: "regressions caught while running a fraction of the suite",
      value: `${r.caught}/${r.total}`,
      note: `RQ3 (${c3}, perf gate of that date: p95 point rule), ${rq3.summary.items_executed_pct.toFixed(0)}% of checks executed on ${rq3.summary.scenarios} PRs`,
    });
  }
  const eff = rq4?.prefix_effect.find((e) => e.max_num_seqs === 32 && e.level === 16);
  const m = (a: Agg | undefined) => a?.median;
  if (eff && m(eff.ttft_p95_off_vs_on_pct) != null) {
    tiles.push({
      label: "p95 TTFT when prefix caching is off (c=16, max-num-seqs 32)",
      value: `${(m(eff.ttft_p95_off_vs_on_pct) as number) > 0 ? "+" : ""}${(m(eff.ttft_p95_off_vs_on_pct) as number).toFixed(0)}%`,
      note: `RQ4 (${c4}), real F1 workload on a laptop RTX 3050 Ti at 780 MHz, ${eff.n_pairs} paired repeats`,
    });
  }
  const r1 = rq5?.attempts.filter((a) => a.scenario === "r1_dynamic_head") ?? [];
  if (r1.length) {
    // name the gate the attempts were decided by: results from different gates are never pooled
    const gmean = r1.every((a) => a.perf.head_vs_base?.metric === "ttft_gmean_ms");
    tiles.push({
      label: "prompt-cache regression repairs verified",
      value: `${r1.filter((a) => a.status === "verified").length}/${r1.length}`,
      note: `RQ5 (${c5}, ${gmean ? "frozen gate: geometric-mean TTFT, 90% run-level interval" : "an earlier p95-based gate rule"}), failing test first, sandbox-validated, full-suite audit`,
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
