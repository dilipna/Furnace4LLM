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
  // the candidate each attempt proposed (or, if none passed, the last one it measured)
  const chosen = att.map((a) => a.candidates.find((c) => c.verdict === "pass") ?? a.candidates[a.candidates.length - 1]);
  const toLog = chosen.length > 0 && chosen.every((c) => c?.strategy.includes("to_log"));
  const rejected = att.flatMap((a) => a.candidates.filter((c) => c.verdict === "fail" && c.perf_summary));
  const pcts = rejected
    .map((c) => /repair [\d.]+ \(\+?(-?[\d.]+)%/.exec(c.perf_summary ?? "")?.[1])
    .filter((x): x is string => x != null)
    .map(Number);
  const footnote =
    rejected.length > 0
      ? `Furnace's first candidate kept the values in the prompt (moved to the end) and was blocked by its own perf gate in ${rejected.length}/${att.length} attempts` +
        (pcts.length ? ` (+${Math.min(...pcts).toFixed(0)}% to +${Math.max(...pcts).toFixed(0)}% p95 vs main)` : "") +
        "."
      : null;
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
      note: `${toLog ? "values logged, no longer sent in the prompt" : "values moved to the end of the user message"} · ${verified}/${att.length} verified`,
      p95: median(cv.map((c) => c.value)),
      runs: cv.map((c) => c.value),
      hit: hits(cv.map((c) => c.prefix_hit_rate?.[1])),
    },
  ];
  return (
    <BeforeAfter stages={stages} n={att.length} footnote={footnote} source={`${REPO}/bench/results/${campaign}/rq5.md`} />
  );
}
