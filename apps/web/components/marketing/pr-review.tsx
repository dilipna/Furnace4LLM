import { PrReviewView, type Trial } from "@/components/marketing/pr-review-view";
import { getRq, latestWith, metricLabel, type GateCompare, type Rq5 } from "@/lib/bench";
// Generated from the scenario's own edits by scripts/export_pr_diff.py (a test checks it is current).
import prDiff from "@/lib/r1-pr-diff.json";

const REPO = "https://github.com/dilipna/Furnace4LLM/blob/main";

/** One file's hunks from a unified diff, headers dropped: "@@", " ", "-" and "+" lines. */
function fileHunks(patch: string, file: string): string[] {
  const out: string[] = [];
  let inFile = false;
  for (const line of patch.split("\n")) {
    if (line.startsWith("--- ")) inFile = line.endsWith(file);
    else if (inFile && !line.startsWith("+++ ") && line !== "") out.push(line);
  }
  return out;
}

const cmp = (c: GateCompare | undefined) =>
  c && {
    baseline: c.baseline,
    value: c.value,
    change: c.change_pct,
    ci: c.ci_pct ?? null,
    verdict: c.verdict,
    hit: c.prefix_hit_rate ?? null,
  };

/**
 * The landing page's centerpiece: one pull request through Furnace, read from the stored RQ5
 * trials (bench/results/<campaign>/rq5.json). Every figure is per trial, compared inside that
 * trial's interleaved runs, as the gate compares them. Recorded, and labeled as such.
 */
export async function PrReview() {
  const campaign = await latestWith("rq5").catch(() => null);
  const rq5 = campaign ? await getRq<Rq5>(campaign, "rq5").catch(() => null) : null;
  const att = (rq5?.attempts ?? []).filter((a) => a.scenario === "r1_dynamic_head" && a.perf.head_vs_base);
  if (!campaign || !att.length) return <PrReviewView trials={[]} prDiff={null} metric="" campaign={null} source="" />;

  const trials: Trial[] = att.map((a) => {
    const chosen = a.candidates.find((c) => c.verdict === "pass");
    const first = a.candidates[0];
    const repairHunks = fileHunks(a.patch ?? "", "app/prompts.py");
    const perf = a.perf as typeof a.perf & { candidate_vs_head?: GateCompare };
    return {
      repeat: a.repeat,
      status: a.status,
      repairDiff: repairHunks.length ? repairHunks : null,
      strategy: chosen?.strategy.replace("rule:prefix_stability.", "") ?? null,
      firstRejected:
        first && first !== chosen
          ? { strategy: first.strategy.replace("rule:prefix_stability.", ""), verdict: first.verdict ?? "fail" }
          : null,
      reproOk: !!(a.repro?.head_fails && a.repro?.base_passes),
      head: cmp(a.perf.head_vs_base),
      repairVsMain: a.status === "verified" ? cmp(a.perf.candidate_vs_base) : null,
      repairVsPr: a.status === "verified" ? cmp(perf.candidate_vs_head) : null,
      judgeSkipped: (a.audit?.items ?? []).some((i) => i.key.startsWith("judge") && i.verdict === "skip"),
      auditFailures: a.audit?.new_failures.length ?? null,
    };
  });

  return (
    <PrReviewView
      trials={trials}
      prDiff={prDiff.files.find((f) => f.path === "app/prompts.py")?.lines ?? null}
      metric={metricLabel(att[0].perf.head_vs_base?.metric)}
      campaign={campaign}
      source={`${REPO}/bench/results/${campaign}/rq5.md`}
    />
  );
}
