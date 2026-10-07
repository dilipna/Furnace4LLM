import { LabelQueue } from "@/components/evals/label-queue";
import { AppHeader } from "@/components/ui/app-header";
import { getRq, latestWith } from "@/lib/bench";

export const dynamic = "force-dynamic";

type Rq2 = {
  seeded: {
    meta: { gold_questions_with_retrieval_miss: number; gold_total: number };
    per_check: Record<string, { recall: number | null; precision: number | null; fpr: number | null; tp: number; fn: number; fp: number; tn: number }>;
    blind_spots: { n: number; check_passed: number };
  };
  human: { status: string; n?: number; ungrounded?: number; citation_check_as_ungrounded_detector?: { recall: number | null; fpr: number | null; tp: number; fn: number; fp: number; tn: number } };
  judge: { status: string; reason?: string };
};

const f3 = (v: number | null | undefined) => (v == null ? "–" : v.toFixed(3));

export default async function EvalsPage() {
  const campaign = await latestWith("rq2");
  const rq2 = campaign ? await getRq<Rq2>(campaign, "rq2") : null;
  const h = rq2?.human;
  const m = h?.citation_check_as_ungrounded_detector;

  return (
    <div className="flex min-h-full flex-col">
      <AppHeader active="/evals" />
      <main className="mx-auto w-full max-w-[1280px] flex-1 px-4 py-8 sm:px-6">
        <div className="border-b border-line pb-6">
          <p className="text-[12px] text-fg-3">Evaluations · fixture support-rag-py (F1)</p>
          <h1 className="mt-1 font-display text-[28px] font-semibold tracking-[-0.02em]">Evaluators and labels</h1>
          <p className="mt-2 max-w-[760px] text-[13px] text-fg-2">
            Deterministic checks are tested against seeded failures. A semantic judge is only trusted after it agrees with
            human labels on a held-out split, so labels come first.
          </p>
        </div>

        {rq2 && (
          <section className="mt-8" aria-labelledby="seeded">
            <h2 id="seeded" className="text-[15px] font-medium">
              Deterministic checks on seeded failures
            </h2>
            <p className="mt-1 text-[12px] text-fg-3">
              Mutation operators with a known effect on each check&apos;s specification, applied to real F1 answers and the 34
              documented answers. This verifies detection, not agreement with human judgment.
            </p>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[640px] border-collapse text-[12px]">
                <thead>
                  <tr className="border-b border-line text-left text-fg-3">
                    <th className="py-2 pr-4 font-normal">check</th>
                    <th className="py-2 pr-4 text-right font-normal">recall</th>
                    <th className="py-2 pr-4 text-right font-normal">precision</th>
                    <th className="py-2 pr-4 text-right font-normal">FPR</th>
                    <th className="py-2 pr-4 text-right font-normal">seeded failures</th>
                    <th className="py-2 text-right font-normal">clean controls</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(rq2.seeded.per_check).map(([k, v]) => (
                    <tr key={k} className="h-8 border-b border-line">
                      <td className="num pr-4 text-fg-0">{k}</td>
                      <td className="num pr-4 text-right">{f3(v.recall)}</td>
                      <td className="num pr-4 text-right">{f3(v.precision)}</td>
                      <td className="num pr-4 text-right">{f3(v.fpr)}</td>
                      <td className="num pr-4 text-right">{v.tp + v.fn}</td>
                      <td className="num text-right">{v.fp + v.tn}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-[12px] text-warn">
              Blind spot: an answer that cites a retrieved but wrong document passes citation_required in{" "}
              {rq2.seeded.blind_spots.check_passed}/{rq2.seeded.blind_spots.n} seeded cases. That needs the judge.
            </p>
            <div className="mt-6 grid gap-4 sm:grid-cols-2">
              <div className="border-l border-line pl-4">
                <div className="text-[11px] text-fg-3">citation check vs human &quot;grounded&quot;</div>
                {h?.status === "labeled" && m ? (
                  <div className="num mt-0.5 text-[13px] text-fg-0">
                    recall {f3(m.recall)}, FPR {f3(m.fpr)} on {h.n} labels ({h.ungrounded} ungrounded)
                  </div>
                ) : (
                  <div className="mt-0.5 text-[13px] text-fg-1">pending labels</div>
                )}
              </div>
              <div className="border-l border-line pl-4">
                <div className="text-[11px] text-fg-3">LLM judge (ungrounded answer)</div>
                <div className="mt-0.5 text-[13px] text-fg-1">
                  {rq2.judge.status === "not_run" ? "draft: not run (needs a Groq/OpenRouter key and labels)" : rq2.judge.status}
                </div>
              </div>
            </div>
            <p className="mt-2 text-[11px] text-fg-3">
              Source: <span className="num">bench/results/{campaign}/rq2.json</span>. After labeling, run{" "}
              <span className="num">uv run poe bench-rq2</span> to recompute.
            </p>
          </section>
        )}

        <section className="mt-12 border-t border-line pt-8" aria-labelledby="queue">
          <h2 id="queue" className="text-[15px] font-medium">
            Labeling queue
          </h2>
          <p className="mt-1 mb-5 text-[12px] text-fg-3">
            60 real answers sampled by model and question kind. Keys: <span className="num">j/k</span> move,{" "}
            <span className="num">p/f</span> grounded yes/no, <span className="num">c/x/-</span> correct yes/no/n.a.,{" "}
            <span className="num">n</span> note.
          </p>
          <LabelQueue />
        </section>
      </main>
    </div>
  );
}
