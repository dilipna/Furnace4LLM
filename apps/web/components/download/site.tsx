"use client";

import Link from "next/link";
import { useState, useSyncExternalStore } from "react";
import { platformFor, type Installer } from "@/lib/download";
import { Comparison } from "./comparison";
import type { EverydayRecording } from "@/lib/everyday-recording";
import "./site.css";

const subscribe = () => () => {};
const repo = "https://github.com/dilipna/Furnace4LLM";
export function ProductShell({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState("system");
  return <div className="download-site" data-theme={theme}>
    <a className="product-skip" href="#product-main">Skip to content</a>
    <header className="product-header"><Link prefetch={false} href="/" className="product-logo" aria-label="Furnace home"><span aria-hidden="true">F</span> Furnace</Link>
      <nav aria-label="Main navigation"><Link prefetch={false} href="/demo">Tour</Link><Link prefetch={false} href="/docs">Docs</Link><Link prefetch={false} href="/pricing">Pricing</Link><Link prefetch={false} href="/support">Support</Link></nav>
      <button className="theme-button" aria-label="Switch color theme" onClick={() => setTheme((theme === "system" ? window.matchMedia("(prefers-color-scheme: dark)").matches : theme === "dark") ? "light" : "dark")}>◐</button>
    </header>
    <main id="product-main">{children}</main>
    <footer className="product-footer"><div><Link prefetch={false} href="/" className="product-logo"><span aria-hidden="true">F</span> Furnace</Link><p>Private AI for sensitive documents.</p><small>Local application preview · no account required</small></div>
      <div><strong>Product</strong><Link prefetch={false} href="/start">Getting started</Link><Link prefetch={false} href="/releases">Releases & checksums</Link><Link prefetch={false} href="/faq">FAQ</Link></div>
      <div><strong>Project</strong><Link prefetch={false} href="/about">About</Link><Link prefetch={false} href="/security">Security</Link><a href={repo}>Source on GitHub ↗</a><Link prefetch={false} href="/researchers">Advanced / Developers</Link><Link prefetch={false} href="/earlier-work">Earlier work</Link></div>
      <div><strong>Policies</strong><Link prefetch={false} href="/privacy">Privacy policy · draft</Link><Link prefetch={false} href="/terms">Terms · draft</Link><Link prefetch={false} href="/support">Contact & support</Link></div>
    </footer>
  </div>;
}

export function DownloadButton({ installer }: { installer: Installer | null }) {
  const platform = useSyncExternalStore(subscribe, () => platformFor(navigator.userAgent), () => "windows" as const);
  const windows = platform === "windows";
  return <div className="download-block" id="download">
    {installer ? <a className="download-primary" href={windows ? (installer.download_url ?? "/downloads/" + installer.file) : "#platforms"} download={windows || undefined} onClick={windows ? undefined : () => document.getElementById("platforms")?.setAttribute("open", "")}>{windows ? "Download Furnace" : "See download options"}<span aria-hidden="true">↓</span></a>
      : <Link prefetch={false} className="download-primary" href="/releases">Installer build status <span aria-hidden="true">→</span></Link>}
    <p className="download-caption">{installer ? `Windows x64 · ${installer.version} · ${(installer.bytes / 1048576).toFixed(1)} MiB · ${installer.signed ? "Signed" : "Unsigned preview"}` : "Windows installer preview · no public release yet"}</p>
    {installer && <details className="checksum"><summary>Version, build date & SHA-256</summary><dl><dt>Version</dt><dd>{installer.version}</dd>{installer.published_at && <><dt>Released (UTC)</dt><dd>{installer.published_at}</dd></>}<dt>Built (UTC)</dt><dd>{installer.built_at}</dd><dt>Source</dt><dd>{installer.commit}</dd><dt>SHA-256</dt><dd data-testid="checksum">{installer.sha256}</dd></dl><Link prefetch={false} href="/releases">How to verify this download →</Link></details>}
    <details className="platform-options" id="platforms"><summary>Other platforms & requirements</summary>{installer && <p><a href={(installer.download_url ?? "/downloads/" + installer.file)} download>Download for Windows x64</a></p>}<p>Windows x64 is the installer target. Model runs have been recorded on Windows 11 with Docker Desktop. CPU works; NVIDIA is optional.</p><p>macOS and Linux: installer previews not built or verified. <a href={repo + "/blob/main/docs/operations/release-procedure.md"}>Source-based setup ↗</a></p><p>No fixed universal RAM/disk promise: choose a recipe and review its memory, image and weight sizes. <Link prefetch={false} href="/start">See requirements.</Link></p></details>
  </div>;
}

export function ProductHome({ installer, recording }: { installer: Installer | null; recording: EverydayRecording | null }) {
  return <ProductShell><section className="product-hero"><div className="product-kicker"><span /> Private, local, yours</div><h1>Private AI for<br /><em>your documents.</em></h1><p className="product-lede">Summarise, find answers and write on your computer.<br className="desktop-break" /> Keep sensitive work out of a cloud chat.</p><DownloadButton installer={installer} /><p className="hero-note">Free local app. No account or subscription.</p></section>
    <section className="studio-window private-demo" aria-label="Recorded document demonstration"><div className="window-bar"><span aria-hidden="true">● ● ●</span><span>Furnace · a private document workspace</span><span>Recorded, not live</span></div>{recording ? <><video controls preload="metadata" poster="/product/generated/everyday/home.png" aria-label="Recorded local document summary and privacy receipt"><source src="/product/generated/everyday/journey.webm" type="video/webm"/><track kind="captions" src="/product/generated/everyday/captions.vtt" srcLang="en" label="English" default/></video><p>Actual installed-app recording · {recording.model} · {recording.accelerator === "nvidia" ? "NVIDIA GPU" : "CPU"}. Synthetic document; recorded output, not a promise of accuracy. <Link prefetch={false} href="/demo">Explore the steps and evidence →</Link></p></> : <div className="recording-pending"><h2>A document in. An answer and its checks out.</h2><p>The real-model recording is not staged in this build. No simulated answer is shown as model evidence.</p><Link prefetch={false} href="/demo">See the recording status and walkthrough →</Link></div>}</section>
    <section className="product-features" aria-labelledby="features-title"><div className="section-intro"><p className="product-kicker">EVERYDAY HELP, ON YOUR TERMS</p><h2 id="features-title">The useful part of AI.<br />Closer to your own files.</h2></div><div className="feature-grid">{[
      ["01", "Make a long page shorter", "Choose a document or paste text. Get a summary, find dates, or ask a specific question."],
      ["02", "Find the next step", "Turn meeting notes into action items, simplify a paragraph, draft a reply or translate a section."],
      ["03", "Inspect the privacy checks", "Each completed answer includes a receipt for the local model’s identity and observed isolation settings."],
      ["04", "Stay in control", "Approve setup and downloads. Clear the conversation when finished. There is no cloud-AI fallback."],
    ].map(([number, title, text]) => <article key={number}><span>{number}</span><h3>{title}</h3><p>{text}</p></article>)}</div></section>
    <section className="product-features scenarios" aria-labelledby="uses-title"><div className="section-intro"><p className="product-kicker">WHAT PEOPLE COULD USE IT FOR</p><h2 id="uses-title">For the work you would<br />rather keep to yourself.</h2><p>Illustrative examples, not testimonials or recorded customer outcomes.</p></div><div className="scenario-grid">{[
      ["Study notes", "Turn a reading into a short outline, then check the original for context."],
      ["Client briefs", "Pull out deliverables and dates without pasting the brief into a cloud chatbot."],
      ["Meeting notes", "Find action items and their owners before drafting a follow-up."],
      ["Invoices", "Locate an amount or due date. Verify it against the document before acting."],
      ["Workplace policies", "Ask where a policy mentions a deadline. Check with the responsible person."],
      ["Personal paperwork", "Simplify a letter or draft a reply. Important decisions still need human review."],
    ].map(([title,text])=><article key={title}><h3>{title}</h3><p>{text}</p></article>)}</div></section>
    <Comparison />
    <section className="product-next"><p className="product-kicker">PRIVATE DOES NOT MEAN INFALLIBLE</p><h2>Keep the original. Check the answer.</h2><p>Local AI can miss details or invent them. The receipt checks the model’s setup and identity; it does not certify the answer or monitor every program on your computer.</p><div><Link prefetch={false} className="product-secondary" href="/start">Start with a document →</Link><Link prefetch={false} href="/security">Understand the privacy boundary →</Link><Link prefetch={false} href="/researchers">Advanced / Developers →</Link></div></section>
  </ProductShell>;
}

export function DocPage({ title, eyebrow = "FURNACE GUIDE", children }: { title: string; eyebrow?: string; children: React.ReactNode }) {
  return <ProductShell><article className="product-doc"><p className="product-kicker">{eyebrow}</p><h1>{title}</h1>{children}</article></ProductShell>;
}
