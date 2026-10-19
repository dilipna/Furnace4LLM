"use client";
import { useState } from "react";
import study from "@/lib/prefix-study.json";
import s from "./evidence-home.module.css";

export function PrefixWorkbench() {
  const [layout, setLayout] = useState<"first" | "last">("first");
  const fixed = layout === "last";
  const row = study.conditions.find((item) => item.id === (fixed ? "D" : "C"))!;
  const metadata = (
    <div className={s.volatile}>
      <span>{fixed ? "02" : "01"}</span>
      <code>session_id + timestamp</code>
      <em>{fixed ? "same paired values" : "unique each request"}</em>
    </div>
  );
  return (
    <div className={s.workbench}>
      <div className={s.workbenchTop}>
        <span>
          <i />
          <i />
          <i />
        </span>
        <span>PROMPT / CACHE INSPECTOR</span>
        <span className={s.recorded}>RECORDED</span>
      </div>
      <div className={s.workbenchBody}>
        <div className={s.workbenchLabel}>
          <span>SYSTEM PROMPT</span>
          <span>Qwen2.5-0.5B</span>
        </div>
        <div
          className={s.layoutToggle}
          role="group"
          aria-label="Recorded prompt layout"
        >
          <button
            type="button"
            aria-pressed={!fixed}
            onClick={() => setLayout("first")}
          >
            Metadata first <span>01</span>
          </button>
          <button
            type="button"
            aria-pressed={fixed}
            onClick={() => setLayout("last")}
          >
            Metadata last <span>02</span>
          </button>
        </div>
        <div className={s.promptBlocks}>
          {!fixed && metadata}
          <div className={s.shared}>
            <span>{fixed ? "01" : "02"}</span>
            <div>
              <code>shared_operations_runbook</code>
              <div className={s.codeLines}>
                <i />
                <i />
                <i />
                <i />
              </div>
              <small>1,500 identical tokens</small>
            </div>
          </div>
          {fixed && metadata}
        </div>
        <div className={s.cacheState}>
          <span className={fixed ? s.greenDot : s.orangeDot} />
          <span>
            {fixed ? "Shared prefix preserved" : "Shared prefix interrupted"}
          </span>
          <strong>
            {((row.cacheRate ?? 0) * 100).toFixed(0)}% token reuse
          </strong>
        </div>
        <div className={s.latency} aria-live="polite" aria-atomic="true">
          <div>
            <span>TIME TO FIRST TOKEN</span>
            <strong>
              {row.p50.toFixed(2)}
              <small> ms</small>
            </strong>
            <p>median run p50 · 3 repeats</p>
          </div>
          <div className={s.latencyVisual}>
            <div
              style={{ width: `${(row.p50 / study.conditions[2].p50) * 100}%` }}
            />
            <span>{fixed ? "94% token reuse" : "0% token reuse"}</span>
          </div>
        </div>
        <p className={s.workbenchFoot}>
          Explore saved measurements. This control does not run inference.
        </p>
      </div>
      <div className={s.workbenchBottom}>
        <span>RTX 3050 Ti / 4 GB</span>
        <span>60 REQUESTS × 3 RUNS</span>
      </div>
    </div>
  );
}
