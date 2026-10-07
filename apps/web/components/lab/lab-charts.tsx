"use client";

import { useMemo, useState } from "react";
import { LineChart, type Series } from "@/components/charts/line-chart";
import { type Agg, parseConfig, type Rq4Row } from "@/lib/bench";

type Metric = "ttft_p95_ms" | "goodput_rps" | "tpot_p50_ms" | "output_tok_s";

const CHARTS: { metric: Metric; title: string; subtitle: string; fmt: (v: number) => string }[] = [
  { metric: "ttft_p95_ms", title: "TTFT p95", subtitle: "ms, lower is better", fmt: (v) => `${Math.round(v).toLocaleString()}` },
  { metric: "goodput_rps", title: "SLO goodput", subtitle: "requests/s meeting the TTFT SLO, higher is better", fmt: (v) => v.toFixed(1) },
  { metric: "tpot_p50_ms", title: "TPOT p50", subtitle: "ms per output token", fmt: (v) => v.toFixed(1) },
  { metric: "output_tok_s", title: "Output throughput", subtitle: "tokens/s", fmt: (v) => `${Math.round(v).toLocaleString()}` },
];

function pt(a: Agg | undefined) {
  return { y: a?.median ?? null, lo: a?.min ?? null, hi: a?.max ?? null };
}

export function LabCharts({ rows, slo }: { rows: Rq4Row[]; slo: number }) {
  const seqsOptions = useMemo(() => [...new Set(rows.map((r) => parseConfig(r.config).seqs))].sort((a, b) => a - b), [rows]);
  const [seqs, setSeqs] = useState(seqsOptions.includes(32) ? 32 : seqsOptions[0]);
  const levels = useMemo(() => [...new Set(rows.map((r) => r.level))].sort((a, b) => a - b), [rows]);
  const repeats = Math.max(0, ...rows.map((r) => r.repeats.length));

  const series = (metric: Metric): Series[] =>
    [true, false].map((pc) => ({
      id: pc ? "on" : "off",
      label: pc ? "prefix cache on" : "prefix cache off",
      color: pc ? "var(--viz-base)" : "var(--viz-focus)",
      points: levels.map((lv) =>
        pt(rows.find((r) => r.level === lv && parseConfig(r.config).prefixCache === pc && parseConfig(r.config).seqs === seqs)?.[metric]),
      ),
    }));

  return (
    <div>
      <div className="flex flex-wrap items-center gap-3" role="radiogroup" aria-label="vLLM max-num-seqs">
        <span className="text-[12px] text-fg-3">max-num-seqs</span>
        {seqsOptions.map((s) => (
          <button
            key={s}
            role="radio"
            aria-checked={s === seqs}
            onClick={() => setSeqs(s)}
            className={`num rounded-[3px] border px-2.5 py-1 text-[12px] transition-colors duration-150 ${
              s === seqs ? "border-line-strong bg-bg-3 text-fg-0" : "border-line text-fg-2 hover:text-fg-0"
            }`}
          >
            {s}
          </button>
        ))}
        <span className="text-[12px] text-fg-3">
          · {repeats} repeat{repeats === 1 ? "" : "s"} per point · SLO TTFT ≤ {slo} ms
        </span>
      </div>
      <div className="mt-5 grid gap-8 md:grid-cols-2">
        {CHARTS.map((c) => (
          <LineChart
            key={c.metric}
            title={c.title}
            subtitle={c.subtitle}
            xs={levels}
            xLabel="concurrency"
            series={series(c.metric)}
            format={c.fmt}
            rangeNote="Line: median across repeats. Band: min-max across repeats."
          />
        ))}
      </div>
    </div>
  );
}
