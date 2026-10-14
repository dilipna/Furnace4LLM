import { getRq, latestWith } from "@/lib/bench";

type Step = { step: string; ok: boolean; seconds?: number; out?: Record<string, unknown> };
type LiveRun = { repo: string; manifest: { started_at: string }; steps: Step[]; verdict: string };
type Verify = { verdict: string; results: { check: string; ok: boolean }[] };
type Webhook = { ok: boolean; steps: { step: string; ok: boolean; out?: Record<string, unknown> }[] };
type Cmp = { change_pct: number; ci_pct?: [number, number] };

const pct = (x: number) => `${x > 0 ? "+" : ""}${x.toFixed(1)}%`;

/** The recorded run on real GitHub (bench/results/<date>-live-github), with links to the PRs. */
export async function LiveGithub() {
  const campaign = await latestWith("live_github").catch(() => null);
  if (!campaign) return null;
  const [run, ver] = await Promise.all([
    getRq<LiveRun>(campaign, "live_github").catch(() => null),
    getRq<Verify>(campaign, "live_verify").catch(() => null),
  ]);
  if (!run) return null;
  // the fresh-commit webhook run, recorded separately (newest campaign that has one)
  const whCampaign = await latestWith("live_webhook").catch(() => null);
  const wh = whCampaign ? await getRq<Webhook>(whCampaign, "live_webhook").catch(() => null) : null;
  const whStep = (n: string) => wh?.steps.find((s) => s.step === n && s.ok)?.out;
  const whCheck = whStep("check") as { url?: string; conclusion?: string; head_sha?: string } | undefined;
  const step = (n: string) => run.steps.find((s) => s.step === n);
  const pr = (n: string) => (step(n)?.out?.pr as { url?: string } | undefined)?.url ?? (step(n)?.out?.url as string | undefined);
  const guard = step("guard")?.out as { check_id?: number; conclusion?: string; title?: string } | undefined;
  const perf = (step("repair")?.out?.perf ?? {}) as { head_vs_base?: Cmp; candidate_vs_base?: Cmp };
  const okCount = ver?.results.filter((r) => r.ok).length ?? 0;
  const rows: [string, string, string | undefined][] = [
    ["Forge", "draft PR with the checks, validated in a sandbox first", pr("forge")],
    ["The regression", "a pull request adding a request id to the system prompt", pr("r1_pr")],
    [
      "Guard",
      `check run on the PR’s head commit: ${guard?.conclusion ?? "–"}${guard?.title ? `, “${guard.title}”` : ""}`,
      guard?.check_id ? `https://github.com/${run.repo}/runs/${guard.check_id}` : undefined,
    ],
    [
      "Repair",
      perf.candidate_vs_base && perf.head_vs_base
        ? `draft fix: ${pct(perf.candidate_vs_base.change_pct)} vs main (90% interval ${perf.candidate_vs_base.ci_pct ? `${pct(perf.candidate_vs_base.ci_pct[0])} to ${pct(perf.candidate_vs_base.ci_pct[1])}` : "–"}), while the PR measured ${pct(perf.head_vs_base.change_pct)}`
        : "draft fix",
      pr("repair"),
    ],
  ];
  if (wh?.ok && whCheck) {
    rows.push([
      "Webhook",
      `a new commit (${whCheck.head_sha?.slice(0, 7)}) on a fresh PR: GitHub’s signed event queued a new Guard run, whose check landed on that exact commit (${whCheck.conclusion}); redeliveries of the event changed nothing`,
      whCheck.url,
    ]);
  }
  return (
    <section aria-labelledby="gh-h" className="border-t border-line">
      <div className="mx-auto grid w-full max-w-[1100px] gap-10 px-4 py-16 sm:px-6 lg:grid-cols-12">
        <div className="lg:col-span-4">
          <p className="num text-[11.5px] tracking-[0.1em] text-ember uppercase">On real GitHub</p>
          <h2 id="gh-h" className="mt-3 font-display text-[28px] leading-tight font-semibold tracking-[-0.02em]">
            The same flow, on a public repository
          </h2>
          <p className="mt-4 text-[14px] leading-relaxed text-fg-2">
            Recorded {run.manifest.started_at.slice(0, 10)} on{" "}
            <a className="underline decoration-line-strong underline-offset-2 hover:text-fg-0" href={`https://github.com/${run.repo}`}>
              {run.repo}
            </a>
            . One live trial on a laptop GPU, not a rate. {ver ? `An independent check of GitHub afterwards passed ${okCount} of ${ver.results.length} items (permissions, token scope, commit, drafts, untouched branches, webhooks).` : ""}
          </p>
        </div>
        <ol className="space-y-3 lg:col-span-8">
          {rows.map(([t, d, href], i) => (
            <li key={t} className="flex gap-4 rounded-[8px] border border-line bg-bg-1 px-5 py-4">
              <span className="num pt-0.5 text-[12px] text-ember">{String(i + 1).padStart(2, "0")}</span>
              <div className="min-w-0 flex-1">
                <p className="text-[14px] font-medium text-fg-0">{t}</p>
                <p className="mt-1 text-[13px] text-fg-2">{d}</p>
              </div>
              {href && (
                <a href={href} className="shrink-0 self-center text-[13px] text-fg-1 underline decoration-line-strong underline-offset-2 hover:text-fg-0">
                  Open on GitHub
                </a>
              )}
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
