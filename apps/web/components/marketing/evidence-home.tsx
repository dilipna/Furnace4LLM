import Link from "next/link";
import { Faq } from "./faq";
import { PrefixWorkbench } from "./prefix-workbench";
import s from "./evidence-home.module.css";
import { Wordmark } from "@/components/ui/wordmark";
import study from "@/lib/prefix-study.json";
import { loadStory } from "@/lib/story";
import { dynamicUnlessRecorded } from "@/lib/render";

const REPO = "https://github.com/dilipna/Furnace4LLM";
const SOURCE = `${REPO}/tree/main/experiments/prefix-cache`;
function Arrow() {
  return <span aria-hidden="true">↗</span>;
}

export default async function EvidenceHome() {
  await dynamicUnlessRecorded();
  const story = await loadStory();
  const gate = story?.gate;
  return (
    <div className={s.home}>
      <a className={s.skip} href="#main">
        Skip to content
      </a>
      <header className={s.header}>
        <Link href="/" aria-label="Furnace home">
          <Wordmark size={17} />
        </Link>
        <nav aria-label="Main" className={s.nav}>
          <Link href="/prefix-check">Prefix checker</Link>
          <a href="#experiment">Experiment</a>
          <Link href="/bench">Evidence</Link>
          <a href={REPO} className={s.sourceLink}>
            GitHub <Arrow />
          </a>
        </nav>
      </header>
      <main id="main">
        <section className={s.hero} aria-labelledby="hero-title">
          <div>
            <p className={s.eyebrow}>
              <span className={s.signal} /> PUBLIC INFERENCE ENGINEERING
            </p>
            <h1 id="hero-title">
              Ship the prompt.
              <br />
              <span>Keep the speed.</span>
            </h1>
            <p className={s.intro}>
              A small prompt edit can erase your cache advantage. Furnace checks
              Python LLM applications before merge, so latency regressions have
              somewhere to stop.
            </p>
            <div className={s.actions}>
              <Link href="/prefix-check" className={s.primary}>
                Try the prefix checker <Arrow />
              </Link>
              <Link href="/demo" className={s.secondary}>
                Watch the recorded demo <Arrow />
              </Link>
            </div>
            <p className={s.heroNote}>
              Built by <a href="https://github.com/dilipna">Dilip Nallamasa</a>{" "}
              · Independent project
            </p>
          </div>
          <PrefixWorkbench />
        </section>
        <div className={s.stack} aria-label="Project stack">
          <span>BUILT AROUND THE SERVING STACK</span>
          {[
            "Python",
            "vLLM",
            "OpenAI-compatible APIs",
            "GitHub Checks",
            "Docker",
          ].map((item) => (
            <strong key={item}>{item}</strong>
          ))}
        </div>
        <section
          id="experiment"
          className={s.section}
          aria-labelledby="experiment-title"
        >
          <div className={s.sectionHeading}>
            <div>
              <p className={s.eyebrow}>01 / THE EXPERIMENT</p>
              <h2 id="experiment-title">
                Same runbook.
                <br />
                Different place for the metadata.
              </h2>
            </div>
            <p>
              A timestamp at the beginning breaks the shared prefix. Move it to
              the end, and the reusable work returns. Four conditions isolate
              the effect.
            </p>
          </div>
          <div className={s.studyGrid}>
            <div className={s.finding}>
              <span className={s.eyebrow}>OBSERVED ON THIS WORKLOAD</span>
              <strong>
                {study.reductionPercent.toFixed(1)}
                <span>%</span>
              </strong>
              <p>
                lower median run p50 TTFT
                <br />
                with metadata last versus first
              </p>
              <div className={s.miniRule} />
              <small>
                {study.measuredRequests} measured requests
                <br />
                {study.successfulRuns} fresh-server runs · concurrency 1
              </small>
            </div>
            <div className={s.studyTable}>
              <div className={s.tableHeading}>
                <span>RECORDED RESULTS</span>
                <span>{study.measuredDate} / ms</span>
              </div>
              <div className={s.tableScroll}>
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Condition</th>
                      <th scope="col">p50 TTFT</th>
                      <th scope="col">p95 TTFT</th>
                      <th scope="col">Cache reuse</th>
                    </tr>
                  </thead>
                  <tbody>
                    {study.conditions.map((row) => (
                      <tr
                        key={row.id}
                        className={row.id === "D" ? s.highlightRow : undefined}
                      >
                        <th scope="row">
                          <span className={s.conditionId}>{row.id}</span>
                          {row.label}
                        </th>
                        <td>{row.p50.toFixed(2)}</td>
                        <td>{row.p95.toFixed(2)}</td>
                        <td>
                          {row.cacheRate === null
                            ? "Disabled"
                            : `${(row.cacheRate * 100).toFixed(2)}%`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className={s.tableNote}>
                Medians of three run-level statistics. Cache reuse counts
                tokens, not requests. Qwen2.5-0.5B · RTX 3050 Ti, 4 GB.
                Synthetic workload, fixed 32-token outputs.
              </p>
              <a href={`${SOURCE}/writeup.md`} className={s.textLink}>
                Method, exact flags and raw evidence <Arrow />
              </a>
            </div>
          </div>
          <details className={s.runDetails}>
            <summary>
              Inspect every run, including the tail outlier{" "}
              <span aria-hidden="true">+</span>
            </summary>
            <div className={s.tableScroll}>
              <table>
                <caption>
                  Individual run p50 / p95 TTFT, in milliseconds. No outliers
                  removed.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Condition</th>
                    <th scope="col">Repeat 1</th>
                    <th scope="col">Repeat 2</th>
                    <th scope="col">Repeat 3</th>
                  </tr>
                </thead>
                <tbody>
                  {study.conditions.map((row) => (
                    <tr key={row.id}>
                      <th scope="row">{row.label}</th>
                      {row.runs.map((run) => (
                        <td key={run.repeat}>
                          {run.p50.toFixed(2)} / {run.p95.toFixed(2)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p>
              {study.warmups} warmups excluded. {study.startupFailures} CUDA
              startup failure retained and retried with identical flags. One
              cache-off p95 exceeded 3 seconds. No answer-quality or
              production-impact claim.
            </p>
          </details>
        </section>
        <section id="how" className={s.section} aria-labelledby="how-title">
          <div className={s.sectionHeading}>
            <div>
              <p className={s.eyebrow}>02 / THE REGRESSION LOOP</p>
              <h2 id="how-title">
                From a suspicious diff
                <br />
                to a reviewable decision.
              </h2>
            </div>
            <Link href="/demo" className={s.textLink}>
              Follow a real recorded run <Arrow />
            </Link>
          </div>
          <div className={s.processGrid}>
            {[
              [
                "01",
                "Render the real prompts",
                "Use the application's own rendering path. Compare the base revision and candidate instead of guessing from the diff.",
                "BASE → HEAD",
              ],
              [
                "02",
                "Measure on the same server",
                "Interleave revisions on one endpoint. The gate uses run-level geometric-mean TTFT and a 90% interval.",
                "PASS / BLOCK / INCONCLUSIVE",
              ],
              [
                "03",
                "Test a supported repair",
                "Write the failing regression test first. A rule-based fix must pass the sandbox and gate before a human reviews it.",
                "DRAFT FIX → HUMAN REVIEW",
              ],
            ].map(([number, title, text, foot]) => (
              <article key={number}>
                <span className={s.stepNumber}>{number}</span>
                <h3>{title}</h3>
                <p>{text}</p>
                <span className={s.stepFoot}>{foot}</span>
              </article>
            ))}
          </div>
          <div className={s.commandStrip}>
            <div>
              <span className={s.signal} />
              <strong>
                See the actual Forge test catch the layout regression.
              </strong>
              <span>No GPU or API key required.</span>
            </div>
            <code>python experiments/prefix-cache/rehearse_guard.py</code>
            <a href={`${SOURCE}/guard-demo.md`}>
              Read the walkthrough <Arrow />
            </a>
          </div>
        </section>
        <section className={s.section} aria-labelledby="evidence-title">
          <div className={s.sectionHeading}>
            <div>
              <p className={s.eyebrow}>03 / EVIDENCE, WITH BOUNDARIES</p>
              <h2 id="evidence-title">
                The misses belong
                <br />
                next to the wins.
              </h2>
            </div>
            <Link href="/bench" className={s.textLink}>
              Explore FurnaceBench <Arrow />
            </Link>
          </div>
          {gate && (
            <div className={s.statGrid}>
              {[
                [gate.falseAlarms, gate.n, "false blocks on unchanged code"],
                [gate.blocks, gate.blockN, "known large regressions blocked"],
                [
                  story?.verified,
                  story?.trials,
                  "repairs verified in one repeated scenario",
                ],
                [
                  gate.undecided,
                  gate.gradedN,
                  "small slowdowns left inconclusive",
                ],
              ].map(([value, count, label]) => (
                <div key={String(label)}>
                  <strong>
                    {value}
                    <span>/{count}</span>
                  </strong>
                  <p>{label}</p>
                </div>
              ))}
            </div>
          )}
          <p className={s.evidenceNote}>
            These gate-validation figures come from a separate recorded
            experiment, not the prefix-layout study above. One laptop GPU, one
            small model, limited fixtures. A structural check cannot detect
            disabled caching, and a latency result does not establish answer
            quality.
          </p>
          <div className={s.resourceGrid}>
            <a href={`${REPO}/blob/main/docs/engineering-review.md`}>
              <span>READ THE ENGINEERING</span>
              <h3>
                Five minutes.
                <br />
                Every claim traceable.
              </h3>
              <p>
                Implementation links, statistical choices, and the limits worth
                asking about.
              </p>
              <Arrow />
            </a>
            <Link href="/demo">
              <span>SEE THE PRODUCT</span>
              <h3>
                The diff. The check.
                <br />
                The tested draft fix.
              </h3>
              <p>
                A recorded walkthrough, plus the public GitHub check and repair
                trail.
              </p>
              <Arrow />
            </Link>
            <a href={`${SOURCE}/results.md`}>
              <span>CHECK THE DATA</span>
              <h3>
                Raw requests.
                <br />
                Not just a headline.
              </h3>
              <p>
                Inspect the workload, counters, repeated runs, failures and
                reproduction steps.
              </p>
              <Arrow />
            </a>
          </div>
        </section>
        <section id="faq" className={s.faq}>
          <div>
            <p className={s.eyebrow}>BEFORE YOU ASK</p>
            <h2>
              A narrower tool.
              <br />A clearer claim.
            </h2>
            <p>
              Python applications. Measured on vLLM. Rule-based repair for one
              regression family. No customers or production readiness claimed.
            </p>
          </div>
          <Faq s={story} />
        </section>
        <section className={s.closing}>
          <p className={s.eyebrow}>BUILT TO BE INSPECTED</p>
          <h2>
            Don’t take the headline.
            <br />
            Take a look at the evidence.
          </h2>
          <div className={s.actions}>
            <a href={REPO} className={s.primary}>
              Explore the repository <Arrow />
            </a>
            <Link href="/demo" className={s.secondary}>
              Watch the recorded demo <Arrow />
            </Link>
          </div>
        </section>
      </main>
      <footer className={s.footer}>
        <div>
          <Wordmark size={15} />
          <p>
            Independent inference engineering by Dilip Nallamasa.
            <br />
            Explore recorded benchmarks or check your prompt prefixes locally
            in your browser.
          </p>
        </div>
        <nav aria-label="Footer">
          <Link href="/prefix-check">Prefix checker</Link>
          <Link href="/lab">Inference Lab</Link>
          <Link href="/guard">Guard</Link>
          <a href={`${REPO}/blob/main/docs/claims.md`}>
            Claims ledger <Arrow />
          </a>
          <a href={REPO}>
            Source <Arrow />
          </a>
        </nav>
        <span>PYTHON / vLLM / GITHUB</span>
      </footer>
    </div>
  );
}
