import { BeforeAfter, type Stage } from "@/components/marketing/before-after";
import { getRq, latestWith, metricLabel, type Rq5 } from "@/lib/bench";

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
  const metric = metricLabel(hv[0].metric);
  // The repair bar shows only repairs the gate accepted: a rejected attempt's last candidate is
  // not "Furnace's repair" (2026-10-12: 2 of 3 attempts rejected under the interval rule).
  const ok = att.filter((a) => a.status === "verified");
  const cv = ok.map((a) => a.perf.candidate_vs_base!);
  const hits = (xs: (number | null | undefined)[]) => {
    const v = xs.filter((x): x is number => x != null);
    return v.length ? median(v) : null;
  };
  const verified = ok.length;
  const chosen = ok.map((a) => a.candidates.find((c) => c.verdict === "pass"));
  const toLog = chosen.length > 0 && chosen.every((c) => c?.strategy.includes("to_log"));
  // Only each attempt's FIRST strategy (keep the values, move them to the end) counts as a
  // "first candidate blocked"; later candidates rejected as unproven are reported in rq5.md.
  const firstBlocked = att
    .map((a) => a.candidates[0])
    .filter((c) => c != null && c.verdict === "fail" && c.strategy.includes("to_suffix") && c.perf_summary);
  // summaries: "repair 154.1 (+42.6%" before 2026-10-11, "repair 108.0 -> 154.1 ms (+42.6%" after
  const pcts = firstBlocked
    .map((c) => /repair [\d.]+(?: -> [\d.]+ ms)? \(\+?(-?[\d.]+)%/.exec(c?.perf_summary ?? "")?.[1])
    .filter((x): x is string => x != null)
    .map(Number);
  const footnote =
    firstBlocked.length > 0
      ? `Furnace's first candidate kept the values in the prompt (moved to the end) and was rejected by its own perf gate (blocked or not shown within tolerance) in ${firstBlocked.length}/${att.length} attempts` +
        (pcts.length ? ` (+${Math.min(...pcts).toFixed(0)}% to +${Math.max(...pcts).toFixed(0)}% ${metric} vs main)` : "") +
        "."
      : null;
  const stages: Stage[] = [
    {
      key: "base",
      label: "main",
      note: "static system prompt",
      ms: median(hv.map((h) => h.baseline)),
      runs: hv.map((h) => h.baseline),
      hit: hits(hv.map((h) => h.prefix_hit_rate?.[0])),
    },
    {
      key: "pr",
      label: "PR R1",
      note: "request id + timestamp at the top of the system prompt",
      ms: median(hv.map((h) => h.value)),
      runs: hv.map((h) => h.value),
      hit: hits(hv.map((h) => h.prefix_hit_rate?.[1])),
    },
  ];
  if (cv.length > 0) {
    stages.push({
      key: "repair",
      label: "Furnace repair",
      note: `${toLog ? "values logged, no longer sent in the prompt" : "values moved to the end of the user message"} · verified in ${verified}/${att.length} attempts (only verified shown)`,
      ms: median(cv.map((c) => c.value)),
      runs: cv.map((c) => c.value),
      hit: hits(cv.map((c) => c.prefix_hit_rate?.[1])),
    });
  }
  return (
    <BeforeAfter
      stages={stages}
      metric={metric}
      n={att.length}
      footnote={footnote}
      source={`${REPO}/bench/results/${campaign}/rq5.md`}
    />
  );
}
