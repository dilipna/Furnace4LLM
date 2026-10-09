import { LabCharts } from "@/components/lab/lab-charts";
import { FurnacePanel } from "@/components/live/furnace-panel";
import { type Reference, RunNow } from "@/components/live/run-now";
import { AppHeader } from "@/components/ui/app-header";
import { apiGet } from "@/lib/api";
import { type Agg, getRq, latestWith, type Rq4, type Workload } from "@/lib/bench";

export const dynamic = "force-dynamic";

const n0 = (v: number | null | undefined) => (v == null ? "–" : Math.round(v).toLocaleString());
const pct = (v: number | null | undefined, d = 1) => (v == null ? "–" : `${(v * 100).toFixed(d)}%`);
const rng = (a: Agg, d = 1, sign = true) =>
  a.median == null
    ? "–"
    : `${sign && a.median > 0 ? "+" : ""}${a.median.toFixed(d)} [${a.min?.toFixed(d)}, ${a.max?.toFixed(d)}]`;

function Fact({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="border-l border-line pl-4">
      <div className="text-[11px] text-fg-3">{label}</div>
      <div className="num mt-0.5 text-[15px] text-fg-0">{value}</div>
      {note && <div className="text-[11px] text-fg-3">{note}</div>}
    </div>
  );
}

export default async function LabPage() {
  const campaign = await latestWith("rq4");
  const [rq4, wl, notes] = await Promise.all([
    campaign ? getRq<Rq4>(campaign, "rq4") : null,
    apiGet<Workload>("/api/bench/workload").catch(() => null),
    campaign ? apiGet<{ notes_md: string | null }>(`/api/bench/campaigns/${campaign}`).catch(() => null) : null,
  ]);

  const clocks = rq4?.clocks ?? [];
  const sm = clocks.map((c) => c.sm_clock_mhz_mean);
  const hitOn = rq4?.rows.filter((r) => r.config.startsWith("pc-on") && r.prefix_hit_rate.median != null) ?? [];
  const configs = rq4 ? [...new Set(rq4.rows.map((r) => r.config))].sort() : [];
  const levels = rq4 ? [...new Set(rq4.rows.map((r) => r.level))].sort((a, b) => a - b) : [];
  const p95At = (cfg: string, lv: number) => rq4?.rows.find((r) => r.config === cfg && r.level === lv)?.ttft_p95_ms.median ?? null;
  const reference: Reference[] = [1, 2, 4, 8].map((lv) => ({ level: lv, on: p95At("pc-on_seqs-32", lv), off: p95At("pc-off_seqs-32", lv) }));

  return (
    <div className="flex min-h-full flex-col">
      <AppHeader active="/lab" />
      <main className="mx-auto w-full max-w-[1280px] flex-1 px-4 py-8 sm:px-6">
        <div className="border-b border-line pb-6">
          <p className="text-[12px] text-fg-3">Inference Lab · fixture support-rag-py (F1)</p>
          <h1 className="mt-1 font-display text-[28px] font-semibold tracking-[-0.02em]">
            Serving sweep on the real workload
          </h1>
          <p className="mt-2 max-w-[760px] text-[13px] text-fg-2">
            F1&apos;s traffic was fingerprinted from its own call log, then replayed against vLLM with prefix caching on
            and off and three scheduler sizes. Every number on this page is read from{" "}
            <span className="num text-fg-1">bench/results/{campaign ?? "…"}</span>; nothing is simulated except where
            labeled.
          </p>
        </div>

        <div className="mt-6 grid gap-6 xl:grid-cols-2">
          <FurnacePanel compact />
          <RunNow reference={reference} campaign={campaign} />
        </div>

        {!rq4 && (
          <p className="mt-8 text-[13px] text-fg-2">
            No RQ4 results yet. Run <span className="num text-fg-1">uv run poe bench-rq4</span> on a machine with a GPU.
          </p>
        )}

        {rq4 && (
          <>
            <section aria-labelledby="cond" className="mt-6 rounded-[6px] border border-line bg-bg-1 px-5 py-4">
              <h2 id="cond" className="text-[12px] text-fg-3">
                Conditions
              </h2>
              <p className="num mt-1 text-[12px] text-fg-1">
                {rq4.manifest.gpu} ({rq4.manifest.memory_mb} MB) · {rq4.engine?.engine} {rq4.engine?.engine_version} ·{" "}
                {rq4.manifest.model} · image {rq4.manifest.image_digest?.split("@")[1]?.slice(0, 19) ?? "–"} · commit{" "}
                {rq4.manifest.git?.sha?.slice(0, 10)}
              </p>
              {sm.length > 0 && (
                <p className="mt-1 text-[12px] text-fg-2">
                  GPU SM clock during runs{" "}
                  <span className="num text-fg-0">
                    {n0(Math.min(...sm))}–{n0(Math.max(...sm))} MHz
                  </span>{" "}
                  (spread {rq4.clock_spread_pct?.toFixed(1)}%), all runs on AC:{" "}
                  {clocks.every((c) => c.on_ac) ? "yes" : "no"}. Comparisons between configs share this clock; absolute
                  latencies depend on it.
                </p>
              )}
              {notes?.notes_md && (
                <details className="mt-2 text-[12px] text-fg-2">
                  <summary className="cursor-pointer text-fg-1">Campaign notes</summary>
                  <pre className="mt-2 font-sans whitespace-pre-wrap text-fg-2">{notes.notes_md}</pre>
                </details>
              )}
            </section>

            {wl && (
              <section aria-labelledby="wl" className="mt-8">
                <h2 id="wl" className="text-[15px] font-medium">
                  Workload fingerprint{" "}
                  <span className="ml-2 rounded-[3px] border border-line px-1.5 py-0.5 text-[11px] font-normal text-fg-2">
                    from {wl.spec.n_observed} real traces
                  </span>
                </h2>
                <div className="mt-4 grid grid-cols-2 gap-y-5 sm:grid-cols-3 lg:grid-cols-6">
                  <Fact label="prompt tokens p50 / p95" value={`${n0(wl.spec.input_tokens.p50)} / ${n0(wl.spec.input_tokens.p95)}`} />
                  <Fact label="output tokens p50 / p95" value={`${n0(wl.spec.output_tokens.p50)} / ${n0(wl.spec.output_tokens.p95)}`} />
                  <Fact label="shared prefix" value={`${n0(rq4.workload.shared_prefix_tokens)} tok`} note="system prompt, every request" />
                  <Fact label="prefix reuse (trace replay)" value={pct(wl.spec.prefix.reuse_ratio_infinite)} note="block hash, 16-token blocks" />
                  <Fact label="arrival" value={`${wl.spec.arrival.mean_rps.toFixed(2)} req/s`} note={`CV ${wl.spec.arrival.cv_interarrival.toFixed(2)}, peak concurrency ${wl.spec.arrival.peak_concurrency}`} />
                  <Fact
                    label="prefix-cache hit, predicted → measured"
                    value={`${pct(rq4.workload.expected_prefix_hit_rate)} → ${
                      hitOn.length ? `${pct(Math.min(...hitOn.map((r) => r.prefix_hit_rate.min ?? 1)))}–${pct(Math.max(...hitOn.map((r) => r.prefix_hit_rate.max ?? 0)))}` : "–"
                    }`}
                    note="vLLM metrics, caching on"
                  />
                </div>
                <p className="mt-3 text-[11px] text-fg-3">
                  The replay generator draws prompt lengths and output lengths from this fingerprint (outputs are fixed per
                  request with ignore_eos), so load shape is synthetic while every distribution is measured. Source:{" "}
                  <span className="num">{wl.source}</span>
                </p>
              </section>
            )}

            <section aria-labelledby="sweep" className="mt-10">
              <h2 id="sweep" className="mb-4 text-[15px] font-medium">
                Sweep: prefix caching on vs off
              </h2>
              <LabCharts rows={rq4.rows} slo={rq4.slo_ttft_p95_ms} />
            </section>

            <section aria-labelledby="eff" className="mt-10">
              <h2 id="eff" className="text-[15px] font-medium">
                Paired effect of turning prefix caching off
              </h2>
              <p className="mt-1 text-[12px] text-fg-3">
                Same seed (same request sequence) within each repeat; median [min, max] over repeats.
              </p>
              <div className="mt-3 overflow-x-auto">
                <table className="w-full min-w-[640px] border-collapse text-[12px]">
                  <thead>
                    <tr className="border-b border-line text-left text-fg-3">
                      <th className="py-2 pr-4 font-normal">max-num-seqs</th>
                      <th className="py-2 pr-4 font-normal">concurrency</th>
                      <th className="py-2 pr-4 text-right font-normal">TTFT p95 change, %</th>
                      <th className="py-2 pr-4 text-right font-normal">goodput lost, req/s</th>
                      <th className="py-2 pr-4 text-right font-normal">pairs</th>
                      <th className="py-2 font-normal">same sign in every pair</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rq4.prefix_effect.map((e) => (
                      <tr key={`${e.max_num_seqs}-${e.level}`} className="h-8 border-b border-line">
                        <td className="num pr-4">{e.max_num_seqs}</td>
                        <td className="num pr-4">{e.level}</td>
                        <td className="num pr-4 text-right text-fg-0">{rng(e.ttft_p95_off_vs_on_pct, 0)}</td>
                        <td className="num pr-4 text-right text-fg-0">{rng(e.goodput_on_minus_off_rps, 2)}</td>
                        <td className="num pr-4 text-right">{e.n_pairs}</td>
                        <td className={e.consistent_sign ? "text-fg-1" : "text-warn"}>{e.consistent_sign ? "yes" : "no"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section aria-labelledby="tbl" className="mt-10">
              <details>
                <summary id="tbl" className="cursor-pointer text-[13px] text-fg-1">
                  Table view: every config and level
                </summary>
                <div className="mt-3 overflow-x-auto">
                  <table className="w-full min-w-[900px] border-collapse text-[12px]">
                    <thead>
                      <tr className="border-b border-line text-left text-fg-3">
                        <th className="py-2 pr-3 font-normal">config</th>
                        <th className="py-2 pr-3 font-normal">c</th>
                        {["TTFT p50", "TTFT p95", "TTFT p99", "TPOT p50", "E2E p95", "req/s", "goodput", "tok/s", "hit rate", "failures"].map((h) => (
                          <th key={h} className="py-2 pr-3 text-right font-normal">
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {configs.flatMap((cfg) =>
                        levels.map((lv) => {
                          const r = rq4.rows.find((x) => x.config === cfg && x.level === lv);
                          if (!r) return null;
                          const m = (a: Agg, d = 0) => (a.median == null ? "–" : a.median.toFixed(d));
                          return (
                            <tr key={`${cfg}-${lv}`} className="h-8 border-b border-line">
                              <td className="num pr-3 text-fg-1">{cfg}</td>
                              <td className="num pr-3">{lv}</td>
                              <td className="num pr-3 text-right">{m(r.ttft_p50_ms)}</td>
                              <td className="num pr-3 text-right text-fg-0">{m(r.ttft_p95_ms)}</td>
                              <td className="num pr-3 text-right">{m(r.ttft_p99_ms)}</td>
                              <td className="num pr-3 text-right">{m(r.tpot_p50_ms, 1)}</td>
                              <td className="num pr-3 text-right">{m(r.e2e_p95_ms)}</td>
                              <td className="num pr-3 text-right">{m(r.throughput_rps, 2)}</td>
                              <td className="num pr-3 text-right">{m(r.goodput_rps, 2)}</td>
                              <td className="num pr-3 text-right">{m(r.output_tok_s)}</td>
                              <td className="num pr-3 text-right">{pct(r.prefix_hit_rate.median)}</td>
                              <td className="num pr-3 text-right">{pct(r.failure_rate.median)}</td>
                            </tr>
                          );
                        }),
                      )}
                    </tbody>
                  </table>
                </div>
              </details>
              {rq4.launch_failures.length > 0 && (
                <p className="mt-4 text-[12px] text-warn">
                  Launch failures: {rq4.launch_failures.map((f) => `${f.config} r${f.repeat}`).join(", ")}
                </p>
              )}
            </section>
          </>
        )}
      </main>
    </div>
  );
}
