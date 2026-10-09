import Link from "next/link";
import { notFound } from "next/navigation";
import { DiffView } from "@/components/guard/diff-view";
import { GuardLive } from "@/components/guard/guard-live";
import { Verdict } from "@/components/guard/verdict";
import { AppHeader } from "@/components/ui/app-header";
import { apiGet } from "@/lib/api";
import { type GateCompare, getRq, latestWith, type RepairAttempt, type Rq3, type Rq5 } from "@/lib/bench";

export const dynamic = "force-dynamic";

function perfRow(name: string, c: GateCompare | undefined) {
  if (!c) return null;
  const hit = c.prefix_hit_rate ?? [null, null];
  return (
    <tr className="h-8 border-b border-line">
      <td className="pr-4 text-fg-1">{name}</td>
      <td className="num pr-4 text-right">{c.baseline.toLocaleString()}</td>
      <td className="num pr-4 text-right text-fg-0">{c.value.toLocaleString()}</td>
      <td className="num pr-4 text-right text-fg-0">
        {c.change_pct > 0 ? "+" : ""}
        {c.change_pct.toFixed(1)}%
      </td>
      <td className="num pr-4 text-right">
        {hit[0] == null ? "–" : `${Math.round(hit[0] * 100)}%`} → {hit[1] == null ? "–" : `${Math.round(hit[1] * 100)}%`}
      </td>
      <td className="pr-4">{c.separated == null ? "–" : c.separated ? "separated" : "overlap"}</td>
      <td>
        <Verdict v={c.verdict} />
      </td>
    </tr>
  );
}

function Attempt({ a, open }: { a: RepairAttempt; open: boolean }) {
  return (
    <details open={open} className="border-b border-line py-4">
      <summary className="flex cursor-pointer flex-wrap items-center gap-3">
        <span className="text-[13px] text-fg-0">Repair attempt, repeat {a.repeat}</span>
        <Verdict v={a.status} />
        <span className="num text-[12px] text-fg-3">{Math.round(a.repair_seconds)} s</span>
        {a.audit && (
          <span className="flex items-center gap-1.5 text-[12px] text-fg-3">
            full-suite audit <Verdict v={a.audit.conclusion} />
          </span>
        )}
      </summary>

      <ol className="mt-4 border-l border-line">
        {a.stages.map((s, i) => (
          <li key={`${s.stage}-${i}`} className="relative pb-3 pl-5">
            <span className="absolute top-[7px] -left-[4px] h-[7px] w-[7px] rounded-full bg-fg-3" aria-hidden="true" />
            <div className="flex flex-wrap items-baseline gap-x-3">
              <span className="num w-[52px] text-[11px] text-fg-3">{s.t.toFixed(1)}s</span>
              <span className="num text-[12px] text-fg-1">{s.stage}</span>
            </div>
            <p className="text-[12px] break-words text-fg-2 sm:ml-[64px]">{s.msg}</p>
          </li>
        ))}
      </ol>

      {a.repro && (
        <p className="mt-2 text-[12px] text-fg-2">
          Failing test first: fails on the PR head <b className="text-fg-0">{String(a.repro.head_fails)}</b>, passes on
          the base revision <b className="text-fg-0">{String(a.repro.base_passes)}</b>.
        </p>
      )}

      {(a.perf.head_vs_base || a.perf.candidate_vs_base) && (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[720px] border-collapse text-[12px]">
            <thead>
              <tr className="border-b border-line text-left text-fg-3">
                <th className="py-2 pr-4 font-normal">revision</th>
                <th className="py-2 pr-4 text-right font-normal">base p95 TTFT, ms</th>
                <th className="py-2 pr-4 text-right font-normal">p95 TTFT, ms</th>
                <th className="py-2 pr-4 text-right font-normal">change</th>
                <th className="py-2 pr-4 text-right font-normal">prefix-cache hit</th>
                <th className="py-2 pr-4 font-normal">runs</th>
                <th className="py-2 font-normal">gate</th>
              </tr>
            </thead>
            <tbody>
              {perfRow("PR head", a.perf.head_vs_base)}
              {perfRow("repair", a.perf.candidate_vs_base)}
            </tbody>
          </table>
        </div>
      )}

      {a.audit && a.audit.items.some((i) => i.verdict !== "pass") && (
        <ul className="mt-3 space-y-1 text-[12px]">
          {a.audit.items
            .filter((i) => i.verdict !== "pass")
            .map((i) => (
              <li key={i.key} className="flex flex-wrap gap-2">
                <Verdict v={i.verdict} />
                <span className="num text-fg-1">{i.key}</span>
                <span className="text-fg-3">{i.detail}</span>
              </li>
            ))}
        </ul>
      )}

      {a.patch && (
        <div className="mt-4">
          <p className="mb-2 text-[12px] text-fg-3">Draft PR diff (fix + regression test)</p>
          <DiffView patch={a.patch} />
        </div>
      )}
      {!a.patch && Object.keys(a.logs).length > 0 && (
        <pre className="mt-3 text-[12px] whitespace-pre-wrap text-fg-2">
          {Object.entries(a.logs)
            .map(([k, v]) => `${k}: ${v}`)
            .join("\n")}
        </pre>
      )}
    </details>
  );
}

export default async function GuardScenario({ params }: PageProps<"/guard/[scenario]">) {
  const { scenario } = await params;
  const [c3, c5] = await Promise.all([latestWith("rq3"), latestWith("rq5")]);
  const [rq3, rq5] = await Promise.all([c3 ? getRq<Rq3>(c3, "rq3") : null, c5 ? getRq<Rq5>(c5, "rq5") : null]);
  const r = rq3?.scenarios.find((x) => x.scenario === scenario);
  const attempts = rq5?.attempts.filter((a) => a.scenario === scenario) ?? [];
  if (!r && attempts.length === 0) notFound();
  const check = r && c3 ? await apiGet<{ markdown: string }>(`/api/bench/campaigns/${c3}/rq3/${scenario}/check`).catch(() => null) : null;
  const firstVerified = attempts.findIndex((a) => a.status === "verified");

  return (
    <div className="flex min-h-full flex-col">
      <AppHeader active="/guard" />
      <main className="mx-auto w-full max-w-[1280px] flex-1 px-4 py-8 sm:px-6">
        <Link href="/guard" className="text-[12px] text-fg-3 hover:text-fg-1">
          ← all pull requests
        </Link>
        <div className="mt-2 border-b border-line pb-6">
          <h1 className="num text-[22px] text-fg-0">{scenario}</h1>
          {r && <p className="mt-1 text-[13px] text-fg-2">{r.description}</p>}
          {r && (
            <div className="mt-3 flex flex-wrap items-center gap-3 text-[12px] text-fg-3">
              <span className="flex items-center gap-1.5">
                Guard <Verdict v={r.targeted_conclusion} />
              </span>
              <span className="flex items-center gap-1.5">
                full suite <Verdict v={r.full_conclusion} />
              </span>
              <span>
                change categories: <span className="text-fg-1">{r.categories.join(", ") || "none"}</span>
              </span>
              <span className="num">
                {r.selected.length} checks run, impact analysis {r.impact_seconds.toFixed(1)} s
              </span>
            </div>
          )}
        </div>

        {r && (
          <div className="mt-6">
            <GuardLive scenario={scenario} />
          </div>
        )}

        {r && (
          <section className="mt-8" aria-labelledby="items">
            <h2 id="items" className="text-[15px] font-medium">
              Checks: targeted selection vs full suite
            </h2>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[900px] border-collapse text-[12px]">
                <thead>
                  <tr className="border-b border-line text-left text-fg-3">
                    <th className="py-2 pr-4 font-normal">check</th>
                    <th className="py-2 pr-4 font-normal">selected by Guard</th>
                    <th className="py-2 pr-4 font-normal">result</th>
                    <th className="py-2 pr-4 text-right font-normal">s</th>
                    <th className="py-2 font-normal">detail</th>
                  </tr>
                </thead>
                <tbody>
                  {r.full.map((it) => {
                    const sel = r.selected.includes(it.key);
                    const why = r.skipped.find((s) => s.key === it.key)?.reason;
                    return (
                      <tr key={it.key} className="border-b border-line align-top">
                        <td className="num py-2 pr-4 text-fg-0">{it.key}</td>
                        <td className="py-2 pr-4">
                          {sel ? <span className="text-fg-1">yes</span> : <span className="text-fg-3">no{why ? `: ${why}` : ""}</span>}
                        </td>
                        <td className="py-2 pr-4">
                          <Verdict v={it.verdict} />
                        </td>
                        <td className="num py-2 pr-4 text-right">{it.seconds.toFixed(1)}</td>
                        <td className="py-2 text-fg-2">{it.detail}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {r.missed_fail.length > 0 && (
              <p className="mt-3 text-[12px] text-bad">Missed by targeting: {r.missed_fail.join(", ")}</p>
            )}
            {check && (
              <details className="mt-4">
                <summary className="cursor-pointer text-[12px] text-fg-1">Check run as posted to GitHub (markdown)</summary>
                <pre className="mt-2 overflow-x-auto rounded-[6px] border border-line bg-bg-1 p-4 font-sans text-[12px] whitespace-pre-wrap text-fg-1">
                  {check.markdown}
                </pre>
              </details>
            )}
          </section>
        )}

        {attempts.length > 0 && (
          <section className="mt-10" aria-labelledby="repair">
            <h2 id="repair" className="text-[15px] font-medium">
              Repair timeline
            </h2>
            <p className="mt-1 text-[12px] text-fg-3">
              {attempts.filter((a) => a.status === "verified").length}/{attempts.length} attempts verified. Furnace opens
              a draft pull request; a human merges.
            </p>
            <div className="mt-2">
              {attempts.map((a, i) => (
                <Attempt key={a.repeat} a={a} open={i === (firstVerified >= 0 ? firstVerified : 0)} />
              ))}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
