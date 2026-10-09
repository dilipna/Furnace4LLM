import { BeforeAfter, type Stage } from "@/components/marketing/before-after";
import { getRq, latestWith, type Rq5 } from "@/lib/bench";

const REPO = "https://github.com/dilipna/Furnace4LLM/blob/main";

const median = (xs: number[]) => {
  const s = [...xs].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};

/** The landing hero's evidence: RQ5's R1 attempts, read from bench/results. */
export async function HeroEvidence() {
  const campaign = await latestWith("rq5").catch(() => null);
  const rq5 = campaign ? await getRq<Rq5>(campaign, "rq5").catch(() => null) : null;
  const att = (rq5?.attempts ?? []).filter(
    (a) => a.scenario === "r1_dynamic_head" && a.perf.head_vs_base && a.perf.candidate_vs_base,
  );
  if (!att.length) return null;
  const hv = att.map((a) => a.perf.head_vs_base!);
  const cv = att.map((a) => a.perf.candidate_vs_base!);
  const hits = (xs: (number | null | undefined)[]) => {
    const v = xs.filter((x): x is number => x != null);
    return v.length ? median(v) : null;
  };
  const verified = att.filter((a) => a.status === "verified").length;
  const stages: Stage[] = [
    {
      key: "base",
      label: "main",
      note: "static system prompt",
      p95: median(hv.map((h) => h.baseline)),
      runs: hv.map((h) => h.baseline),
      hit: hits(hv.map((h) => h.prefix_hit_rate?.[0])),
    },
    {
      key: "pr",
      label: "PR R1",
      note: "request id + timestamp at the top of the system prompt",
      p95: median(hv.map((h) => h.value)),
      runs: hv.map((h) => h.value),
      hit: hits(hv.map((h) => h.prefix_hit_rate?.[1])),
    },
    {
      key: "repair",
      label: "Furnace repair",
      note: `values moved to the end of the user message · ${verified}/${att.length} verified`,
      p95: median(cv.map((c) => c.value)),
      runs: cv.map((c) => c.value),
      hit: hits(cv.map((c) => c.prefix_hit_rate?.[1])),
    },
  ];
  return <BeforeAfter stages={stages} n={att.length} source={`${REPO}/bench/results/${campaign}/rq5.md`} />;
}
