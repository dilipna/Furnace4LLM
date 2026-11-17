"use client";

import Link from "next/link";
import { useState } from "react";
import { SiteShell } from "./site-shell";
import s from "./simple-workspace.module.css";

const guides = [
  { title: "Set up Furnace", description: "Check what you need and open your local workspace.", href: "/start", words: "install download start setup windows linux mac python uv computer" },
  { title: "Explore without a model", description: "Open the guided example and prepare your first kit.", href: "/start#example", words: "example demo explore model project free starter kit docker fixture" },
  { title: "Connect a running model server", description: "Learn what the local connector supports and how to use it.", href: "/start#server", words: "connect server endpoint llm model inference local api" },
  { title: "Understand the recorded example", description: "See the saved demonstration and what its results establish.", href: "/demo", words: "recorded demo video results performance evidence latency" },
  { title: "What does Furnace cost?", description: "The local preview is free. Managed hosting is planned.", href: "/pricing", words: "price pricing subscription cost paid hosting infrastructure monthly" },
  { title: "Read the technical research", description: "Inspect the experiment, measurements and limitations.", href: "/research", words: "research benchmark prefix cache transformer study eval evaluation security" },
];
const stopWords = new Set(["i", "a", "an", "the", "want", "to", "my", "how", "do", "does", "can", "me", "for", "with", "is", "it", "and"]);

export default function SimpleHome() {
  const [query, setQuery] = useState("");
  const [submitted, setSubmitted] = useState("");
  const terms = submitted.toLowerCase().split(/\W+/).filter((word) => word && !stopWords.has(word));
  const matches = terms.length ? guides.filter((guide) => terms.some((word) =>
    `${guide.title} ${guide.words}`.toLowerCase().includes(word))) : [];
  return (
    <SiteShell>
      <section className={s.welcome} aria-labelledby="welcome-title">
        <div className={s.welcomeMark} aria-hidden="true">F</div>
        <p className={s.kicker}>YOUR MODEL. YOUR NEXT STEP.</p>
        <h1 id="welcome-title">What would you like to build?</h1>
        <p className={s.intro}>A home for your model’s setup, checks and results.<br />{" "}
          Start with a free local workspace, then take it one step at a time.</p>
        <form className={s.search} role="search" onSubmit={(event) => {
          event.preventDefault(); setSubmitted(query.trim());
        }}>
          <label className={s.srOnly} htmlFor="help-search">Search Furnace setup help</label>
          <input id="help-search" type="search" value={query} maxLength={200}
            placeholder="Find setup help, examples, or results…" onChange={(event) => {
              setQuery(event.target.value);
              if (!event.target.value.trim()) setSubmitted("");
            }} />
          <button type="submit" disabled={!query.trim()} aria-label="Search setup help">↑</button>
        </form>
        <div className={s.suggestions} aria-label="Suggested next steps">
          <Link href="/start">＋ Set up my workspace</Link>
          <Link href="/start#example">▷ Try an example</Link>
          <Link href="/demo">↗ Understand the results</Link>
        </div>
        {submitted && (
          <section className={s.searchResults} aria-label="Setup help results">
            <p role="status">{matches.length
              ? `${matches.length} helpful ${matches.length === 1 ? "guide" : "guides"}`
              : "No matching guides yet. Try “setup”, “server”, or “results”."}</p>
            {matches.map((guide) => (
              <Link key={guide.href} href={guide.href}>
                <span><strong>{guide.title}</strong><span>{guide.description}</span></span>
                <span aria-hidden="true">↗</span>
              </Link>
            ))}
            {!matches.length && <Link href="/start">Browse the getting-started guide ↗</Link>}
          </section>
        )}
        <p className={s.quietNote}>Searches these guides. No AI chat or model execution happens here.</p>
      </section>
      <section id="how" className={s.homeDetails} aria-label="About Furnace">
        <details>
          <summary>What can I do with Furnace?</summary>
          <p>Inspect a model project, save its setup and evaluation cases, and export a starter kit
            in the local Studio application. An optional Docker example checks the infrastructure.
            A separate connector sends requests to a local model server you already operate.</p>
          <p>The Docker example is deterministic and does not run an LLM. Model loading and
            managed hosting are not provided by this preview.</p>
          <Link href="/start">See the setup steps →</Link>
        </details>
        <details id="faq">
          <summary>Do I need a model or a GPU to start?</summary>
          <p>No. You can explore the guided example and export a kit without a model, GPU or Docker.
            Running the infrastructure fixture needs local Linux-container Docker. Real inference
            needs your own compatible server; model/server combinations remain unvalidated.</p>
        </details>
        <a id="experiment" href="/research#experiment">Looking for the prefix-cache experiment? Read the research ↗</a>
      </section>
    </SiteShell>
  );
}
