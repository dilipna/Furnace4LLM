"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

export type Stage = {
  key: "base" | "pr" | "repair";
  label: string;
  note: string;
  p95: number; // median over repeats, ms
  runs: number[]; // each repeat's p95, ms
  hit: number | null; // prefix-cache hit rate, 0..1
};

const STEP_MS = 650;

/**
 * Replayable before/after for the R1 regression: main, the PR, Furnace's verified repair.
 * Every value is from bench/results (RQ5); the animation only reveals them in order.
 */
export function BeforeAfter({
  stages,
  source,
  n,
  footnote,
}: {
  stages: Stage[];
  source: string;
  n: number;
  footnote?: string | null;
}) {
  const [step, setStep] = useState(0);
  const timers = useRef<number[]>([]);

  // Reveal the stages in order; with reduced motion, all at once.
  const schedule = useCallback(() => {
    timers.current.forEach(clearTimeout);
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    timers.current = reduce
      ? [window.setTimeout(() => setStep(stages.length), 0)]
      : stages.map((_, i) => window.setTimeout(() => setStep(i + 1), 250 + i * STEP_MS));
  }, [stages]);

  useEffect(() => {
    schedule();
    return () => timers.current.forEach(clearTimeout);
  }, [schedule]);

  const play = () => {
    setStep(0);
    schedule();
  };

  const max = Math.max(...stages.flatMap((s) => [s.p95, ...s.runs])) * 1.08;
  const base = stages.find((s) => s.key === "base");

  return (
    <figure className="rounded-[6px] border border-line bg-bg-1" aria-label="R1 regression: p95 time to first token and prefix-cache hit rate on main, the PR, and Furnace's repair">
      <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
        <span className="text-[12px] text-fg-2">
          PR R1 · “request id in the system prompt for debugging”
        </span>
        <button
          onClick={play}
          className="rounded-[3px] border border-line px-2 py-0.5 text-[11px] text-fg-2 transition-colors duration-150 hover:border-line-strong hover:text-fg-0"
        >
          Replay
        </button>
      </div>

      <div className="space-y-4 px-4 py-4">
        {stages.map((s, i) => {
          const shown = step > i;
          const regress = s.key === "pr";
          const delta = base && s.key !== "base" ? ((s.p95 - base.p95) / base.p95) * 100 : null;
          return (
            <div key={s.key} className={`transition-opacity duration-300 ${shown ? "opacity-100" : "opacity-30"}`}>
              <div className="flex items-baseline justify-between gap-3">
                <span className="text-[13px] text-fg-0">{s.label}</span>
                <span className="num text-[12px] text-fg-1">
                  {shown ? (
                    <>
                      <span className="text-fg-0">{Math.round(s.p95).toLocaleString()} ms</span>
                      {delta != null && (
                        <span className={regress ? "text-ember" : "text-fg-2"}>
                          {" "}
                          {delta > 0 ? "+" : ""}
                          {delta.toFixed(0)}%
                        </span>
                      )}
                    </>
                  ) : (
                    "…"
                  )}
                </span>
              </div>
              <div className="relative mt-1.5 h-2.5 rounded-[2px] bg-bg-3" aria-hidden="true">
                <div
                  className={`h-full rounded-r-[4px] transition-[width] duration-300 ease-out ${regress ? "bg-ember" : "bg-fg-2"}`}
                  style={{ width: shown ? `${(s.p95 / max) * 100}%` : "0%" }}
                />
                {shown &&
                  s.runs.map((r, j) => (
                    <span
                      key={j}
                      className="absolute top-[-2px] h-[14px] w-px bg-fg-0/70"
                      style={{ left: `${(r / max) * 100}%` }}
                      title={`repeat ${j + 1}: ${r.toFixed(1)} ms`}
                    />
                  ))}
              </div>
              <div className="mt-1.5 flex items-center justify-between text-[11px] text-fg-3">
                <span>{s.note}</span>
                <span className="num">
                  prefix-cache hit{" "}
                  <span className={shown ? (regress ? "text-ember" : "text-fg-1") : ""}>
                    {shown && s.hit != null ? `${Math.round(s.hit * 100)}%` : "–"}
                  </span>
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {footnote && <p className="border-t border-line px-4 py-2.5 text-[11px] leading-relaxed text-fg-2">{footnote}</p>}
      <figcaption className="border-t border-line px-4 py-2.5 text-[11px] leading-relaxed text-fg-3">
        p95 time to first token on the F1 support assistant, laptop RTX 3050 Ti (vLLM, Qwen2.5-0.5B). Bar: median of {n}{" "}
        repeats; ticks: each repeat. Source{" "}
        <Link href="/guard/r1_dynamic_head" className="text-fg-1 underline decoration-line-strong underline-offset-2 hover:text-fg-0">
          repair timeline
        </Link>{" "}
        ·{" "}
        <a href={source} className="num text-fg-1 underline decoration-line-strong underline-offset-2 hover:text-fg-0">
          bench/results/…/rq5.md
        </a>
      </figcaption>
    </figure>
  );
}
