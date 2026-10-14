// The landing page's figures, read from the stored results (bench/results via the API). Every
// number is per trial (compared inside one trial's interleaved runs, as the gate compares them)
// or a count from the gate validation; nothing is typed in by hand.
import { getRq, latestWith, type GateCompare, type Rq5 } from "@/lib/bench";

type GateSet = { trials: number; pass: number; inconclusive: number; warn: number; block: number; change_median: number };

export type Story = {
  campaign: string;
  trials: number;
  verified: number;
  // trial 1 (repeat 0), shown in the hero; the /demo page shows all three
  base: number;
  pr: number;
  repair: number | null;
  prChange: number;
  prCi: [number, number] | null;
  prVerdict: string;
  hitBase: number | null;
  hitPr: number | null;
  hitRepair: number | null;
  repairVsMain: number[]; // per verified trial, %
  repairVsMainUpper: number[]; // 90% upper bounds, %
  repairVsMainLower: number[]; // 90% lower bounds, %
  repairVsPr: number[];
  gate: { campaign: string; n: number; falseAlarms: number; pass: number; blocks: number; blockN: number; blockMedian: number; undecided: number; gradedN: number } | null;
};

const pick = (c: GateCompare | undefined) => c ?? null;

export async function loadStory(): Promise<Story | null> {
  try {
    const campaign = await latestWith("rq5");
    if (!campaign) return null;
    const rq5 = await getRq<Rq5>(campaign, "rq5");
    const att = (rq5?.attempts ?? []).filter((a) => a.scenario === "r1_dynamic_head" && a.perf.head_vs_base);
    if (!att.length) return null;
    const first = att[0];
    const hv = pick(first.perf.head_vs_base)!;
    const ok = att.filter((a) => a.status === "verified");
    const cvs = ok.map((a) => a.perf.candidate_vs_base!).filter(Boolean);
    const chs = ok
      .map((a) => (a.perf as typeof a.perf & { candidate_vs_head?: GateCompare }).candidate_vs_head)
      .filter((c): c is GateCompare => !!c);
    const firstRepair = first.status === "verified" ? first.perf.candidate_vs_base : undefined;

    let gate: Story["gate"] = null;
    const gc = await latestWith("gate_validation");
    const gv = gc ? await getRq<{ sets: Record<string, GateSet> }>(gc, "gate_validation") : null;
    if (gc && gv) {
      const un = ["v1_aa", "v2_restored"].map((k) => gv.sets[k]).filter(Boolean);
      const gr = ["v3b_r2", "v3c_topk4", "v3c_topk8"].map((k) => gv.sets[k]).filter(Boolean);
      const r1 = gv.sets["v3a_r1"];
      gate = {
        campaign: gc,
        n: un.reduce((s, x) => s + x.trials, 0),
        falseAlarms: un.reduce((s, x) => s + x.block + x.warn, 0),
        pass: un.reduce((s, x) => s + x.pass, 0),
        blocks: r1?.block ?? 0,
        blockN: r1?.trials ?? 0,
        blockMedian: r1?.change_median ?? 0,
        undecided: gr.reduce((s, x) => s + x.inconclusive, 0),
        gradedN: gr.reduce((s, x) => s + x.trials, 0),
      };
    }

    return {
      campaign,
      trials: att.length,
      verified: ok.length,
      base: hv.baseline,
      pr: hv.value,
      repair: firstRepair?.value ?? null,
      prChange: hv.change_pct,
      prCi: hv.ci_pct ?? null,
      prVerdict: hv.verdict,
      hitBase: hv.prefix_hit_rate?.[0] ?? null,
      hitPr: hv.prefix_hit_rate?.[1] ?? null,
      hitRepair: firstRepair?.prefix_hit_rate?.[1] ?? null,
      repairVsMain: cvs.map((c) => c.change_pct),
      repairVsMainUpper: cvs.map((c) => c.ci_pct?.[1] ?? NaN),
      repairVsMainLower: cvs.map((c) => c.ci_pct?.[0] ?? NaN),
      repairVsPr: chs.map((c) => c.change_pct),
      gate,
    };
  } catch {
    return null; // API down: the page renders without figures and says so
  }
}
