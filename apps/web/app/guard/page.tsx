import Link from "next/link";
import { Verdict } from "@/components/guard/verdict";
import { AppHeader } from "@/components/ui/app-header";
import { apiGet } from "@/lib/api";
import { getRq, latestWith, type LiveGuard, type Rq3 } from "@/lib/bench";

export const dynamic = "force-dynamic";

function Stat({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="border-l border-line pl-4">
      <div className="text-[11px] text-fg-3">{label}</div>
      <div className="num mt-0.5 text-[18px] text-fg-0">{value}</div>
      {note && <div className="text-[11px] text-fg-3">{note}</div>}
    </div>
  );
}

export default async function GuardPage() {
  const campaign = await latestWith("rq3");
  const [rq3, live] = await Promise.all([
    campaign ? getRq<Rq3>(campaign, "rq3") : null,
    apiGet<LiveGuard[]>("/api/bench/guard-live").catch(() => [] as LiveGuard[]),
  ]);
  const s = rq3?.summary;

  return (
    <div className="flex min-h-full flex-col">
      <AppHeader active="/guard" />
      <main className="mx-auto w-full max-w-[1280px] flex-1 px-4 py-8 sm:px-6">
        <div className="border-b border-line pb-6">
          <p className="text-[12px] text-fg-3">Guard · fixture support-rag-py (F1)</p>
          <h1 className="mt-1 font-display text-[28px] font-semibold tracking-[-0.02em]">Pull request checks</h1>
          <p className="mt-2 max-w-[760px] text-[13px] text-fg-2">
            Each row is a scripted pull request against F1. Guard maps the diff onto the behavior-to-code graph and runs
            only the checks the change can affect. To measure what that costs in missed regressions, the full suite was
            also run on every PR; its failures are the ground truth.
          </p>
        </div>

        {s && rq3 && (
          <>
            <div className="mt-6 grid grid-cols-2 gap-y-5 sm:grid-cols-4">
              <Stat label="suite executed (targeted)" value={`${s.items_executed_pct.toFixed(0)}%`} note={`${s.suite_items}-item suite, ${s.scenarios} PRs`} />
              <Stat
                label="regressions caught"
                value={`${s.regression_recall.caught}/${s.regression_recall.total}`}
                note="FAILs of the full suite also failed by the targeted run"
              />
              <Stat label="wall time full → targeted" value={`${Math.round(s.wall_seconds.full)} → ${Math.round(s.wall_seconds.targeted)} s`} note="all PRs, incl. impact analysis" />
              <Stat label="check conclusion = full suite" value={`${s.conclusion_agreement}/${s.scenarios}`} />
            </div>

            <div className="mt-8 overflow-x-auto">
              <table className="w-full min-w-[900px] border-collapse text-[12px]">
                <thead>
                  <tr className="border-b border-line text-left text-fg-3">
                    <th className="py-2 pr-4 font-normal">pull request</th>
                    <th className="py-2 pr-4 font-normal">change</th>
                    <th className="py-2 pr-4 text-right font-normal">checks run</th>
                    <th className="py-2 pr-4 font-normal">Guard</th>
                    <th className="py-2 pr-4 font-normal">full suite</th>
                    <th className="py-2 pr-4 font-normal">missed by targeting</th>
                    <th className="py-2 text-right font-normal">time, s</th>
                  </tr>
                </thead>
                <tbody>
                  {rq3.scenarios.map((r) => (
                    <tr key={r.scenario} className="h-10 border-b border-line align-middle">
                      <td className="pr-4">
                        <Link href={`/guard/${r.scenario}`} className="num text-fg-0 hover:text-ember-hi">
                          {r.scenario}
                        </Link>
                        <div className="text-[11px] text-fg-3">{r.description}</div>
                      </td>
                      <td className="pr-4 text-fg-2">{r.categories.join(", ") || "–"}</td>
                      <td className="num pr-4 text-right">
                        {r.selected.length}/{s.suite_items}
                        {r.fell_back_to_full ? " (fallback)" : ""}
                      </td>
                      <td className="pr-4">
                        <Verdict v={r.targeted_conclusion} />
                      </td>
                      <td className="pr-4">
                        <Verdict v={r.full_conclusion} />
                        {r.full_fail.length > 0 && <span className="num ml-2 text-[11px] text-fg-2">{r.full_fail.join(", ")}</span>}
                      </td>
                      <td className={`num pr-4 ${r.missed_fail.length ? "text-bad" : "text-fg-3"}`}>
                        {[...r.missed_fail, ...r.missed_warn.map((w) => `${w} (warn)`)].join(", ") || "none"}
                      </td>
                      <td className="num text-right">
                        {Math.round(r.full_seconds)} → {Math.round(r.targeted_seconds)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-[11px] text-fg-3">
              Source: <span className="num">bench/results/{campaign}/rq3.json</span>. The judge item is SKIP in every run
              (no judge key configured); serving-config PRs cannot fail because every revision runs on the same endpoint.
            </p>
          </>
        )}

        {!rq3 && <p className="mt-8 text-[13px] text-fg-2">RQ3 has not finished yet; the earlier single live runs are below.</p>}

        {live.length > 0 && (
          <section className="mt-12" aria-labelledby="live">
            <h2 id="live" className="text-[15px] font-medium">
              Earlier live runs (2026-10-04, one run each)
            </h2>
            <ul className="mt-3 divide-y divide-line border-y border-line">
              {live.map((g) => (
                <li key={g.scenario} className="py-3">
                  <details>
                    <summary className="flex cursor-pointer flex-wrap items-center gap-3">
                      <span className="num text-[13px] text-fg-0">{g.scenario}</span>
                      {g.results.map((r) => (
                        <span key={r.key} className="flex items-center gap-1 text-[11px] text-fg-3">
                          {r.key} <Verdict v={r.verdict} />
                        </span>
                      ))}
                    </summary>
                    {g.check_md && <pre className="mt-3 overflow-x-auto rounded-[6px] border border-line bg-bg-1 p-4 font-sans text-[12px] whitespace-pre-wrap text-fg-1">{g.check_md}</pre>}
                  </details>
                </li>
              ))}
            </ul>
          </section>
        )}
      </main>
    </div>
  );
}
