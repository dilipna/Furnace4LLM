"use client";

import { useState } from "react";

export type StepData = {
  prChange: number | null;
  prCi: [number, number] | null;
  repairVsMain: number | null;
  repairUpper: number | null;
  repairLower: number | null;
  repairVsPr: number | null;
  verified: number;
  trials: number;
};

const pct = (x: number) => `${x > 0 ? "+" : ""}${x.toFixed(1)}%`;

function Panel({ children }: { children: React.ReactNode }) {
  return <div className="rounded-[10px] border border-line-strong bg-bg-1 p-5 sm:p-6">{children}</div>;
}

function Connect() {
  return (
    <Panel>
      <p className="text-[12px] text-fg-3">GitHub App · installed on one repository</p>
      <p className="mt-1 text-[15px] font-medium">your-org / support-assistant</p>
      <ul className="mt-5 space-y-2 text-[12.5px]">
        {[
          ["Code", "read"],
          ["New furnace/* branches", "write"],
          ["Draft pull requests", "write"],
          ["Check runs", "write"],
          ["Organization settings", "none"],
        ].map(([k, v]) => (
          <li key={k} className="flex items-center justify-between border-b border-line pb-2">
            <span className="text-fg-1">{k}</span>
            <span className={`num text-[11.5px] ${v === "none" ? "text-fg-3" : "text-fg-0"}`}>{v}</span>
          </li>
        ))}
      </ul>
      <p className="mt-4 text-[11px] text-fg-3">Never merges. Never pushes to your default branch.</p>
    </Panel>
  );
}

function Measure() {
  const order = ["main", "PR", "main", "PR", "main", "PR"];
  return (
    <Panel>
      <p className="text-[12px] text-fg-3">Same GPU, same server, runs interleaved</p>
      <div className="mt-5 flex items-center gap-2">
        {order.map((o, i) => (
          <div key={i} className="flex-1">
            <div className={`h-12 rounded-[4px] ${o === "PR" ? "bg-ember/80" : "bg-fg-3/60"}`} />
            <p className="num mt-1.5 text-center text-[10.5px] text-fg-2">{o}</p>
          </div>
        ))}
      </div>
      <ul className="mt-6 space-y-2 text-[12.5px] text-fg-1">
        <li>→ Prompts rendered by each revision’s own code</li>
        <li>→ Real questions, never synthetic text</li>
        <li>→ Server cache hit rate read from its metrics</li>
      </ul>
    </Panel>
  );
}

function Decide({ d }: { d: StepData }) {
  // an axis from -10% to +40%; the PR's interval sits far off the right edge
  const x = (v: number) => `${Math.min(100, Math.max(0, ((v + 10) / 50) * 100))}%`;
  return (
    <Panel>
      <p className="text-[12px] text-fg-3">Change in time to first token vs main, 90% interval</p>
      <div className="relative mt-8 h-24">
        <div className="absolute inset-x-0 top-10 h-px bg-line-strong" />
        <div className="absolute top-6 h-8 rounded-[3px] bg-ok/10" style={{ left: x(-10), width: `calc(${x(10)} - ${x(-10)})` }} />
        <div className="absolute top-6 h-8 border-l border-dashed border-warn/70" style={{ left: x(10) }} />
        <div className="absolute top-6 h-8 border-l border-dashed border-bad/70" style={{ left: x(25) }} />
        <span className="num absolute top-0 text-[10px] text-warn" style={{ left: x(10) }}>
          +10% tolerance
        </span>
        <span className="num absolute top-0 text-[10px] text-bad" style={{ left: x(25) }}>
          +25% block
        </span>
        {d.repairLower != null && d.repairUpper != null && (
          <div className="absolute top-[34px] h-3" style={{ left: x(d.repairLower), width: `calc(${x(d.repairUpper)} - ${x(d.repairLower)})` }}>
            <div className="h-full rounded-full bg-ok/80" />
          </div>
        )}
        <div className="absolute top-[34px] right-0 flex h-3 items-center">
          <span className="num mr-2 text-[10.5px] text-ember">PR {d.prChange != null ? pct(d.prChange) : ""} →</span>
          <div className="h-3 w-6 rounded-l-full bg-ember" />
        </div>
        <span className="num absolute top-16 text-[10.5px] text-ok" style={{ left: x(-8) }}>
          repair {d.repairVsMain != null ? pct(d.repairVsMain) : ""}
        </span>
      </div>
      <div className="mt-2 grid grid-cols-3 gap-2 text-center text-[11px]">
        <span className="rounded-[4px] border border-ok/40 py-1.5 text-ok">PASS</span>
        <span className="rounded-[4px] border border-dashed border-unsure/50 py-1.5 text-unsure">INCONCLUSIVE</span>
        <span className="rounded-[4px] border border-bad/40 py-1.5 text-bad">BLOCK</span>
      </div>
      <p className="mt-3 text-[11px] text-fg-3">Too noisy to decide is reported as inconclusive, never as a pass.</p>
    </Panel>
  );
}

function Repair({ d }: { d: StepData }) {
  return (
    <Panel>
      <div className="flex items-center justify-between">
        <p className="text-[12px] text-fg-3">Draft pull request into the PR’s branch</p>
        <span className="num rounded-full border border-line-strong px-2 py-0.5 text-[10.5px] text-fg-2">DRAFT</span>
      </div>
      <p className="mt-1 text-[15px] font-medium">Log the request id instead of sending it</p>
      <ul className="mt-5 space-y-2.5 text-[12.5px]">
        {[
          ["Regression test fails on the PR, passes on main", true],
          ["Existing tests pass", true],
          [`Faster than the PR${d.repairVsPr != null ? ` (${pct(d.repairVsPr)})` : ""}`, true],
          [`Within the block threshold of main${d.repairVsMain != null ? ` (${pct(d.repairVsMain)})` : ""}`, true],
        ].map(([t]) => (
          <li key={t as string} className="flex gap-2.5">
            <span aria-hidden="true" className="text-ok">
              ✓
            </span>
            <span className="text-fg-1">{t}</span>
          </li>
        ))}
        <li className="flex gap-2.5">
          <span aria-hidden="true" className="text-fg-3">
            ○
          </span>
          <span className="text-fg-2">A person reviews and decides</span>
        </li>
      </ul>
      <p className="mt-4 text-[11px] text-fg-3">
        Verified in {d.verified}/{d.trials} repeated trials of one scenario. Other regressions are refused, not guessed.
      </p>
    </Panel>
  );
}

const STEPS = [
  {
    n: "01",
    title: "Connect a repository",
    body: "Install a GitHub App on one repository. Your code and model stay on your machine.",
    bullets: ["Least-privilege, per-job tokens", "Runner on your own GPU box", "Shown on a public GitHub repository"],
  },
  {
    n: "02",
    title: "Measure every pull request",
    body: "Furnace replays main and the PR against your model server, side by side.",
    bullets: ["Only the checks a change can affect", "Your prompts, your server", "Cache reuse measured, not guessed"],
  },
  {
    n: "03",
    title: "Decide with confidence",
    body: "A 90% interval separates real slowdowns from GPU noise before anyone merges.",
    bullets: ["Pass, block or inconclusive", "Design frozen before validation", "Reported on the PR as a check"],
  },
  {
    n: "04",
    title: "Get a tested fix",
    body: "For a supported regression, Furnace drafts the fix and proves it before you see it.",
    bullets: ["Failing test written first", "Same gate checks the fix", "A human always merges"],
  },
];

export function Steps({ d }: { d: StepData }) {
  const [i, setI] = useState(0);
  const visual = [<Connect key="c" />, <Measure key="m" />, <Decide key="d" d={d} />, <Repair key="r" d={d} />][i];
  return (
    <div className="grid gap-10 lg:grid-cols-12 lg:gap-14">
      <div role="tablist" aria-label="How Furnace works" className="space-y-2 lg:col-span-5">
        {STEPS.map((s, j) => (
          <button
            key={s.n}
            role="tab"
            aria-selected={i === j}
            onClick={() => setI(j)}
            className={`block w-full rounded-[8px] border px-5 py-4 text-left transition-colors duration-200 ${
              i === j ? "border-ember/60 bg-bg-1" : "border-transparent hover:bg-bg-1/60"
            }`}
          >
            <div className="flex items-baseline gap-4">
              <span className={`num text-[12px] ${i === j ? "text-ember" : "text-fg-3"}`}>{s.n}</span>
              <span className="font-display text-[19px] font-semibold tracking-[-0.01em]">{s.title}</span>
            </div>
            {i === j && (
              <div className="line-in mt-2 pl-9">
                <p className="text-[14px] leading-relaxed text-fg-2">{s.body}</p>
                <ul className="mt-3 space-y-1.5 text-[13px] text-fg-1">
                  {s.bullets.map((b) => (
                    <li key={b} className="flex gap-2">
                      <span aria-hidden="true" className="text-ember">
                        +
                      </span>
                      {b}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </button>
        ))}
      </div>
      <div role="tabpanel" className="line-in lg:col-span-7 lg:pt-2" key={i}>
        {visual}
      </div>
    </div>
  );
}
