"use client";

import Link from "next/link";
import { useState } from "react";
import { SiteShell } from "./site-shell";
import s from "./simple-workspace.module.css";

const command = "git clone https://github.com/dilipna/Furnace4LLM.git\ncd Furnace4LLM\nuv sync --frozen\nuv run furnace studio";

export default function StartGuide() {
  const [system, setSystem] = useState("");
  const [checked, setChecked] = useState<string[]>([]);
  const [copied, setCopied] = useState("");
  const requirements = ["Git", "Python 3.12", "uv", "Internet access for the first installation"];
  const ready = Boolean(system) && checked.length === requirements.length;
  async function copyCommands() {
    try {
      await navigator.clipboard.writeText(command);
      setCopied("Commands copied. Run them from a new working folder.");
    } catch {
      setCopied("Copy is unavailable. Select the commands below and copy them manually.");
    }
  }
  return (
    <SiteShell><div className={s.guide}>
      <p className={s.kicker}>GET STARTED</p>
      <h1>Your first workspace,<br />one step at a time.</h1>
      <p className={s.intro}>You can start without choosing a model. The current preview runs
        locally on your computer and is free to use.</p>
      <section className={s.guideStep} aria-labelledby="check-title">
        <span className={s.stepNumber}>1</span>
        <div>
          <h2 id="check-title">Check the basics</h2>
          <p>This is a source preview, so it needs a few developer tools. A native installer
            is not available yet.</p>
          <fieldset className={s.systemChoices}>
            <legend>Your operating system</legend>
            {["Windows", "Linux", "macOS"].map((value) => (
              <label key={value}><input type="radio" name="system" value={value}
                checked={system === value} onChange={() => setSystem(value)} />{value}</label>
            ))}
          </fieldset>
          {system === "macOS" && <p className={s.notice}>macOS onboarding has not been verified.
            These instructions are a starting point, not a compatibility confirmation.</p>}
          <div className={s.checklist}>
            {requirements.map((value) => (
              <label key={value}><input type="checkbox" checked={checked.includes(value)}
                onChange={(event) => setChecked(event.target.checked
                  ? [...checked, value] : checked.filter((item) => item !== value))} />{value}</label>
            ))}
          </div>
          <p className={s.small}>These are your confirmations. This website cannot inspect your
            computer. Docker is only needed for the optional infrastructure test.</p>
          <details><summary>Where do I get these tools?</summary><p>
            <a href="https://git-scm.com/downloads">Git</a> · <a href="https://www.python.org/downloads/">Python</a> · <a href="https://docs.astral.sh/uv/getting-started/installation/">uv installation guide</a>
          </p></details>
        </div>
      </section>
      <section className={s.guideStep} aria-labelledby="install-title">
        <span className={s.stepNumber}>2</span>
        <div>
          <h2 id="install-title">Open Furnace on your computer</h2>
          <p>Open a terminal in a new working folder. Run these commands, then keep the terminal open.</p>
          <div className={s.commandBox}>
            <div><span>Source preview</span><button type="button" onClick={copyCommands}>Copy commands</button></div>
            <pre tabIndex={0}>{command}</pre>
          </div>
          <p role="status" className={s.small}>{copied}</p>
          <p className={s.small}>{ready
            ? "Your checklist is complete. The installation still needs to succeed on your computer."
            : "You can read or copy the commands now. Confirm the prerequisites above before running them."}</p>
          <p>Studio prints a private session link. Open that link in your browser. Use Ctrl+C in
            the terminal to stop Studio.</p>
          <p className={s.small}>The commands install the current main source, not a native
            installer. First installation downloads pinned packages. Fresh-profile setup remains
            a verification gate.</p>
        </div>
      </section>
      <section className={s.guideStep} aria-labelledby="choose-title">
        <span className={s.stepNumber}>3</span>
        <div>
          <h2 id="choose-title">Choose your starting point</h2>
          <div className={s.nextSteps}>
            <article id="example"><h3>Just exploring?</h3>
              <p>Choose <strong>Open guided example</strong> in Studio. Inspect the setup and
                export a kit. Opening the example does not start Docker or run a model.</p>
              <p className={s.small}>The optional execution returns deterministic uppercase text.
                Exact matches check the plumbing, not answer quality.</p>
            </article>
            <article><h3>Have a model project?</h3>
              <p>Choose <strong>Add my model project</strong>, enter its folder and save your contract
                and cases. Inspection reads bounded metadata; it does not load weights or
                execute your code.</p>
            </article>
            <article id="server"><h3>Already running a model server?</h3>
              <p>Open <strong>Connect a local model server</strong> in Studio. Save your local
                endpoint and model ID, then explicitly connect and send a sanitized request.</p>
              <p className={s.small}>Only unauthenticated <code>http://127.0.0.1:PORT/v1</code>
                text-chat servers are accepted. Furnace does not start that server or verify its
                weights. This manual connector is separate from Furnace-operated models.</p>
            </article>
            <article id="managed-model"><h3>Want Furnace to run a model locally?</h3>
              <p>Open <strong>Connect a local model server</strong> in Studio and expand
                <strong> Let Furnace run a pinned model</strong>. Choose a recipe and accelerator,
                save the selection, review its download and resource limits, then approve
                <strong> Prepare (download and verify)</strong>. Once prepared, choose
                <strong> Start server</strong>. You can then try a sanitized message or load
                the reference suite and run its checks.</p>
              <p className={s.small}>Requires local Docker with Linux containers, disk space,
                sufficient memory and internet for the first preparation. CPU recipes are available;
                the NVIDIA option additionally requires GPU support in Docker. This runs on your
                machine and does not activate paid cloud hosting. <a href="https://github.com/dilipna/Furnace4LLM/blob/aa24843d6907c99d8810534980fa1e7767f8d223/docs/product/real-model-validation.md">Read the recorded model results and their limits.</a></p>
            </article>
          </div>
        </div>
      </section>
      <section id="help" className={s.help}>
        <h2>A little help, if you need it</h2>
        <details><summary>Can I try something before installing?</summary>
          <p>Yes. <Link href="/demo">Watch the recorded example</Link> or <Link href="/research">read
            the research</Link>. Recorded results are past runs; opening these pages does not execute a model.</p>
        </details>
        <details><summary>Is the $20/month service available?</summary>
          <p>Managed hosting is planned. Billing and cloud provisioning are inactive. The current local preview is free.</p>
        </details>
        <details><summary>Where can I report a setup problem?</summary>
          <p>Use the <a href="https://github.com/dilipna/Furnace4LLM/issues">repository issue tracker</a>.
            Include your operating system and the error, but remove session links, keys, private prompts and other secrets.</p>
        </details>
      </section>
    </div></SiteShell>
  );
}
