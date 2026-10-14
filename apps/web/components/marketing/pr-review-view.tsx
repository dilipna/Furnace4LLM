"use client";

import { useState } from "react";
import { Verdict } from "@/components/guard/verdict";

type Cmp = {
  baseline: number;
  value: number;
  change: number;
  ci: [number, number] | null;
  verdict: string;
  hit: [number | null, number | null] | null;
};

export type Trial = {
  repeat: number;
  status: string;
  repairDiff: string[] | null;
  strategy: string | null;
  firstRejected: { strategy: string; verdict: string } | null;
  reproOk: boolean;
  head: Cmp | null | undefined;
  repairVsMain: Cmp | null | undefined;
  repairVsPr: Cmp | null | undefined;
  judgeSkipped: boolean;
  auditFailures: number | null;
};

const pct = (x: number) => `${x > 0 ? "+" : ""}${x.toFixed(1)}%`;
const hitPct = (h: number | null | undefined) => (h == null ? "–" : `${Math.round(h * 100)}%`);

/** A unified diff excerpt: hunk headers muted, context plain, removals red, additions green. */
function DiffLines({ lines }: { lines: string[] }) {
  return (
    <pre className="num rounded-[3px] border border-line bg-bg-0 py-2 text-[11.5px] leading-[1.6]">
      {lines.map((l, i) => {
        const k = l[0];
        const cls =
          k === "@"
            ? "text-fg-3"
            : k === "-"
              ? "bg-bad/10 text-[#e8a597]"
              : k === "+"
                ? "bg-ok/10 text-[#b9d3a9]"
                : "text-fg-2";
        return (
          <div key={i} className={`py-px pr-3 pl-7 -indent-4 break-all whitespace-pre-wrap ${cls}`}>
            <span aria-hidden="true" className={`mr-2 select-none ${k === "-" ? "text-bad" : k === "+" ? "text-ok" : "text-fg-3"}`}>
              {k === "@" ? "" : k === " " ? " " : k === "-" ? "−" : "+"}
            </span>
            {k === "@" ? l : l.slice(1)}
          </div>
        );
      })}
    </pre>
  );
}

function Bar({ label, ms, max, hit, tone, k }: { label: string; ms: number; max: number; hit: string; tone: "base" | "hot"; k: string }) {
  return (
    <div className="grid grid-cols-[52px_1fr_auto] items-center gap-3 sm:grid-cols-[64px_1fr_auto]">
      <span className="text-[12px] text-fg-1">{label}</span>
      <div className="h-2.5 rounded-[2px] bg-bg-3">
        <div
          key={k}
          className={`bar-fill h-full rounded-[2px] ${tone === "hot" ? "bg-ember" : "bg-fg-3"}`}
          style={{ width: `${Math.max(1.5, (ms / max) * 100)}%` }}
        />
      </div>
      <span className="num text-right text-[12px] text-fg-0 sm:w-[150px]">
        {ms.toFixed(1)} ms
        <span className="block text-[11px] text-fg-3 sm:inline sm:text-[12px]">
          <span className="hidden sm:inline"> · </span>hit {hit}
        </span>
      </span>
    </div>
  );
}

function Step({ n, title, children, last }: { n: number; title: React.ReactNode; children: React.ReactNode; last?: boolean }) {
  return (
    <li className="relative grid grid-cols-[22px_1fr] gap-3 pb-5">
      {!last && <span aria-hidden="true" className="absolute top-6 bottom-0 left-[10.5px] w-px bg-line-strong" />}
      <span className="num z-[1] flex h-[22px] w-[22px] items-center justify-center rounded-full border border-line-strong bg-bg-1 text-[11px] text-fg-2">
        {n}
      </span>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2 text-[13px] font-medium text-fg-0">{title}</div>
        <div className="mt-2 space-y-2">{children}</div>
      </div>
    </li>
  );
}

/** One pull request, measured: change → effect → decision → draft repair → human review. */
export function PrReviewView({
  trials,
  prDiff,
  metric,
  campaign,
  source,
}: {
  trials: Trial[];
  prDiff: string[] | null;
  metric: string;
  campaign: string | null;
  source: string;
}) {
  const [i, setI] = useState(0);
  if (!trials.length) {
    return (
      <div className="rounded-[6px] border border-dashed border-line-strong p-6 text-[13px] text-fg-2">
        The recorded pull-request run is unavailable because the results API did not answer. The walkthrough is in{" "}
        <a className="underline" href="https://github.com/dilipna/Furnace4LLM/blob/main/docs/demo-3min.md">
          docs/demo-3min.md
        </a>
        .
      </div>
    );
  }
  const t = trials[i];
  const h = t.head;
  const rm = t.repairVsMain;
  const rp = t.repairVsPr;
  const max = Math.max(h?.value ?? 0, h?.baseline ?? 0, rm?.value ?? 0) || 1;
  return (
    <figure className="overflow-hidden rounded-[6px] border border-line-strong bg-bg-1">
      <figcaption className="flex flex-wrap items-center justify-between gap-2 border-b border-line bg-bg-2 px-4 py-2.5">
        <span className="num inline-flex items-center gap-2 text-[11px] tracking-wide text-fg-2">
          <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-fg-3" />
          RECORDED RUN · NOT LIVE
        </span>
        <span role="tablist" aria-label="Repeated trial" className="flex items-center gap-1">
          <span className="mr-1 text-[11px] text-fg-3">trial</span>
          {trials.map((x, j) => (
            <button
              key={x.repeat}
              role="tab"
              aria-selected={j === i}
              onClick={() => setI(j)}
              className={`num h-6 min-w-6 rounded-[3px] border px-1.5 text-[11px] transition-colors duration-150 ${
                j === i ? "border-ember bg-ember-lo text-fg-0" : "border-line-strong text-fg-2 hover:text-fg-0"
              }`}
            >
              {j + 1}
            </button>
          ))}
        </span>
      </figcaption>

      <div className="px-4 pt-4 sm:px-5">
        <p className="text-[11px] text-fg-3">Scripted pull request into main · fixture app F1 (support assistant)</p>
        <p className="mt-1 text-[14px] font-medium text-fg-0">“Add request id and timestamp to the system prompt for debugging”</p>
      </div>

      <ol className="px-4 pt-4 sm:px-5">
        <Step n={1} title={<>The change <span className="num text-[11px] font-normal text-fg-3">app/prompts.py · build_messages</span></>}>
          {prDiff ? <DiffLines lines={prDiff} /> : null}
          <p className="text-[12px] text-fg-2">
            Answers stay the same, so output-quality evals pass. But every request now starts with different text,
            so the server can no longer reuse its cached prompt prefix.
          </p>
        </Step>

        {h && (
          <Step n={2} title={<>Measured on the model server <span className="num text-[11px] font-normal text-fg-3">{metric}</span></>}>
            <div className="space-y-2">
              <Bar k={`b${i}`} label="main" ms={h.baseline} max={max} hit={hitPct(h.hit?.[0])} tone="base" />
              <Bar k={`h${i}`} label="this PR" ms={h.value} max={max} hit={hitPct(h.hit?.[1])} tone="hot" />
            </div>
            <p className="num text-[12px] text-fg-1">
              {pct(h.change)} <span className="text-fg-3">90% interval {h.ci ? `${pct(h.ci[0])} to ${pct(h.ci[1])}` : "–"}</span>
            </p>
          </Step>
        )}

        {h && (
          <Step n={3} title={<>Decision <Verdict v={h.verdict} /></>}>
            <p className="text-[12px] text-fg-2">
              {h.verdict === "block"
                ? "The whole interval is above the 10% tolerance and the change exceeds the 25% block threshold. The check run fails; nothing is merged."
                : h.verdict === "inconclusive"
                  ? "The interval is too wide to decide. The check reports that instead of passing the PR."
                  : `Gate verdict: ${h.verdict}.`}
            </p>
          </Step>
        )}

        <Step n={4} title={<>Draft repair {t.status === "verified" ? <Verdict v="verified" /> : <Verdict v={t.status} />}</>}>
          {t.firstRejected && (
            <p className="text-[12px] text-fg-2">
              Tried first and rejected by the same gate: <code className="num text-fg-1">{t.firstRejected.strategy}</code> (kept the
              values in the prompt). Then <code className="num text-fg-1">{t.strategy}</code>:
            </p>
          )}
          {t.repairDiff && t.status === "verified" ? (
            <details className="group">
              <summary className="num cursor-pointer list-none text-[12px] text-fg-2 select-none hover:text-fg-0">
                <span aria-hidden="true" className="mr-1.5 inline-block transition-transform duration-150 group-open:rotate-90">
                  ▸
                </span>
                app/prompts.py <span className="text-ok">+{t.repairDiff.filter((l) => l.startsWith("+")).length}</span>{" "}
                <span className="text-bad">−{t.repairDiff.filter((l) => l.startsWith("-")).length}</span>
                <span className="text-fg-3"> · show the repair diff</span>
              </summary>
              <div className="mt-2">
                <DiffLines lines={t.repairDiff} />
              </div>
            </details>
          ) : null}
          {rm && rp && (
            <>
              <Bar k={`r${i}`} label="repair" ms={rm.value} max={max} hit={hitPct(rm.hit?.[1])} tone="base" />
              <dl className="num grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[12px]">
                <dt className="text-fg-3">vs this PR</dt>
                <dd className="text-fg-0">
                  {pct(rp.change)} <span className="text-fg-3">interval {rp.ci ? `${pct(rp.ci[0])} to ${pct(rp.ci[1])}` : "–"} · must be below 0%</span>
                </dd>
                <dt className="text-fg-3">vs main</dt>
                <dd className="text-fg-0">
                  {pct(rm.change)} <span className="text-fg-3">worst case {rm.ci ? pct(rm.ci[1]) : "–"} · must stay below +25%</span>
                </dd>
              </dl>
            </>
          )}
          <ul className="space-y-1 text-[12px] text-fg-2">
            <li>{t.reproOk ? "✓" : "✕"} regression test written first: fails on this PR, passes on main</li>
            <li>
              {t.auditFailures === 0 ? "✓ every executed check passed on the repaired tree" : "audit: see report"}
              {t.judgeSkipped && <span className="text-fg-3"> · LLM judge skipped (no key), not counted as a pass</span>}
            </li>
          </ul>
        </Step>

        <Step n={5} last title={<>Human review <Verdict v="pending" /></>}>
          <p className="text-[12px] text-fg-2">
            Opened as a draft pull request into the PR’s branch. Furnace never merges. The repair logs the request id
            instead of sending it, so the reviewer decides whether that is acceptable.
          </p>
        </Step>
      </ol>

      <p className="border-t border-line px-4 py-3 text-[11px] leading-relaxed text-fg-3 sm:px-5">
        Trial {i + 1} of {trials.length} repeated trials of this one scenario (fixture F1, regression R1). Laptop RTX 3050 Ti,
        vLLM, Qwen2.5-0.5B, concurrency 8, 3 interleaved runs per revision, campaign {campaign}.{" "}
        <a className="underline decoration-line-strong underline-offset-2 hover:text-fg-1" href={source}>
          Raw results
        </a>
      </p>
    </figure>
  );
}
