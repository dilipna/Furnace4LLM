import Link from "next/link";
import { type Agg, campaigns, getRq, type Rq4, type Rq5 } from "@/lib/bench";

type Micro = Record<string, { tp: number; n_truth: number } | undefined>;
type Rq1 = { micro: Record<string, Micro> };
type GateSet = { trials: number; pass: number; inconclusive: number; warn: number; block: number; change_median: number };
type GateValidation = { sets: Record<string, GateSet> };
type Findings = { pooled: { matched: number; emitted: number; expected: number } };

/** Held-out set 6's single first scan (docs/scanner-eval-set6.md), pinned so a rescan never replaces it. */
const HELD_OUT_FIRST_SCAN = "2026-10-13-set6";

type Tile = { value: string; label: string; note: string };

function Tiles({ tiles, muted }: { tiles: Tile[]; muted?: boolean }) {
  return (
    <div className="grid gap-x-8 gap-y-8 sm:grid-cols-2 lg:grid-cols-4">
      {tiles.map((t) => (
        <div key={t.label} className={`border-l pl-4 ${muted ? "border-line" : "border-ember/60"}`}>
          <div className={`font-display text-[30px] font-semibold tracking-[-0.02em] ${muted ? "text-fg-1" : "text-fg-0"}`}>{t.value}</div>
          <div className="mt-1 text-[13px] text-fg-1">{t.label}</div>
          <div className="mt-1 text-[11px] leading-relaxed text-fg-3">{t.note}</div>
        </div>
      ))}
    </div>
  );
}

/** Headline FurnaceBench numbers, each read from its result file. Renders nothing if the API is down. */
export async function BenchStrip() {
  let list;
  try {
    list = await campaigns();
  } catch {
    return null;
  }
  const latest = (rq: string) => list.find((c) => c.available.includes(rq))?.name;
  const [cg, c4, c5] = [latest("gate_validation"), latest("rq4"), latest("rq5")];
  const [gate, rq4, rq5, set6, findings] = await Promise.all([
    cg ? getRq<GateValidation>(cg, "gate_validation").catch(() => null) : null,
    c4 ? getRq<Rq4>(c4, "rq4").catch(() => null) : null,
    c5 ? getRq<Rq5>(c5, "rq5").catch(() => null) : null,
    getRq<Rq1>(HELD_OUT_FIRST_SCAN, "rq1").catch(() => null),
    getRq<Findings>(HELD_OUT_FIRST_SCAN, "set6_findings").catch(() => null),
  ]);

  const proven: Tile[] = [];
  const limits: Tile[] = [];
  if (gate) {
    // unchanged-code sets as planned before any trial (docs/gate-revision.md): V1 A/A + V2 restored
    const unchanged = ["v1_aa", "v2_restored"].map((k) => gate.sets[k]).filter(Boolean);
    const n = unchanged.reduce((s, x) => s + x.trials, 0);
    const falseFail = unchanged.reduce((s, x) => s + x.block + x.warn, 0);
    const pass = unchanged.reduce((s, x) => s + x.pass, 0);
    if (n) {
      proven.push({
        value: `${falseFail}/${n}`,
        label: "false alarms on unchanged code",
        note: `Perf gate, fresh validation after its design was frozen: PASS ${pass}/${n}, the rest INCONCLUSIVE (${cg})`,
      });
    }
    const r1 = gate.sets["v3a_r1"];
    if (r1) {
      proven.push({
        value: `${r1.block}/${r1.trials}`,
        label: "times the prompt-cache regression was blocked",
        note: `Regression R1 on fixture F1, median change +${r1.change_median.toFixed(0)}% geometric-mean TTFT (${cg})`,
      });
    }
    const graded = ["v3b_r2", "v3c_topk4", "v3c_topk8"].map((k) => gate.sets[k]).filter(Boolean);
    const gn = graded.reduce((s, x) => s + x.trials, 0);
    if (gn) {
      const meds = graded.map((x) => x.change_median);
      limits.push({
        value: `${graded.reduce((s, x) => s + x.inconclusive, 0)}/${gn}`,
        label: "small regressions left undecided",
        note: `Graded changes measured +${Math.min(...meds).toFixed(0)}% to +${Math.max(...meds).toFixed(0)}% (set medians), below what they were sized for. Catching regressions just above the 10% tolerance is not shown`,
      });
    }
  }
  const att = rq5?.attempts.filter((a) => a.scenario === "r1_dynamic_head") ?? [];
  if (att.length) {
    proven.push({
      value: `${att.filter((a) => a.status === "verified").length}/${att.length}`,
      label: "repairs verified, repeated trials of one scenario",
      note: `Fixture F1, regression R1, rule-based. Not a rate over apps or regression types (${c5})`,
    });
  }
  const eff = rq4?.prefix_effect.find((e) => e.max_num_seqs === 32 && e.level === 16);
  const m = (a: Agg | undefined) => a?.median;
  if (eff && m(eff.ttft_p95_off_vs_on_pct) != null) {
    const v = m(eff.ttft_p95_off_vs_on_pct) as number;
    proven.push({
      value: `${v > 0 ? "+" : ""}${v.toFixed(0)}%`,
      label: "p95 time to first token with prefix caching off",
      note: `Concurrency 16, real F1 workload, laptop RTX 3050 Ti at 780 MHz, ${eff.n_pairs} paired repeats (${c4})`,
    });
  }
  const ho = set6?.micro["held-out-6"]?.llm_call_sites;
  if (ho?.n_truth) {
    limits.push({
      value: `${ho.tp}/${ho.n_truth}`,
      label: "LLM call sites found in five unseen apps",
      note: "Held-out first scan, labels committed before it. Misses: unsupported SDKs and agent runners",
    });
  }
  if (findings) {
    const f = findings.pooled;
    limits.push({
      value: `${f.matched}/${f.emitted}`,
      label: "scanner findings that were right",
      note: `Same apps; recall ${f.matched}/${f.expected}. Scanner findings are advisory, never a gate`,
    });
  }
  // A recorded live run lives in bench/results/<date>-live-github/ (docs/github-app.md).
  if (!list.some((c) => c.name.endsWith("-live-github"))) {
    limits.push({
      value: "0",
      label: "live GitHub runs recorded",
      note: "The GitHub App path is tested against a mock API; the real run on a demo repository is pending",
    });
  }
  if (!proven.length) return null;

  return (
    <section className="border-t border-line" aria-labelledby="bench-strip">
      <div className="mx-auto w-full max-w-[1200px] px-4 py-16 sm:px-6">
        <div className="flex flex-wrap items-baseline justify-between gap-4">
          <h2 id="bench-strip" className="font-display text-[24px] font-semibold tracking-[-0.01em]">
            What the evidence supports, and where it stops
          </h2>
          <Link href="/bench" className="text-[13px] text-fg-2 hover:text-fg-0">
            Every campaign and correction →
          </Link>
        </div>
        <p className="mt-2 max-w-[720px] text-[13px] text-fg-2">
          Every figure is read from a result file in the repository. One laptop GPU, one small model, two fixture apps.
        </p>
        <div className="mt-10">
          <Tiles tiles={proven} />
        </div>
        <h3 className="mt-12 mb-6 text-[12px] tracking-wide text-fg-3 uppercase">Limits, measured the same way</h3>
        <Tiles tiles={limits} muted />
      </div>
    </section>
  );
}
