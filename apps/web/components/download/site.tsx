"use client";

import Link from "next/link";
import { useState, useSyncExternalStore } from "react";
import { platformFor, type Installer } from "@/lib/download";
import Image from "next/image";
import captured from "@/public/product/researcher-home-source.json";
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
    <footer className="product-footer"><div><Link prefetch={false} href="/" className="product-logo"><span aria-hidden="true">F</span> Furnace</Link><p>Infrastructure for model researchers.</p><small>Local application preview · no account required</small></div>
      <div><strong>Product</strong><Link prefetch={false} href="/start">Getting started</Link><Link prefetch={false} href="/releases">Releases & checksums</Link><Link prefetch={false} href="/faq">FAQ</Link></div>
      <div><strong>Project</strong><Link prefetch={false} href="/about">About</Link><Link prefetch={false} href="/security">Security</Link><a href={repo}>Source on GitHub ↗</a><Link prefetch={false} href="/researchers">Model compatibility</Link><Link prefetch={false} href="/earlier-work">Earlier work</Link></div>
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

export function ProductHome({ installer }: { installer: Installer | null }) {
  return <ProductShell>
    <section className="product-hero"><div className="product-kicker"><span /> Infrastructure for model researchers</div><h1>You build the model.<br /><em>Give it a foundation.</em></h1><p className="product-lede">Connect your model. Get a free infrastructure starter kit.<br className="desktop-break" /> Bring serving, security controls, evaluations, logs and recovery together.</p><DownloadButton installer={installer} /><p className="hero-note">Free starter kit and local Studio · Managed service proposed at $20/month</p></section>
    <section className="studio-window" aria-label="Researcher workspace preview"><div className="window-bar"><span aria-hidden="true">● ● ●</span><span>Furnace Studio · your model workspace</span><span>Recorded, not live</span></div><Image unoptimized src="/product/researcher-home.png" alt="Actual researcher Studio source-preview capture with test metadata; no model inference" width={captured.width} height={captured.height} /><p>Actual source-preview capture with test metadata; no model inference. <Link prefetch={false} href="/demo">Explore the recorded model journey →</Link></p></section>
    <section className="product-features" aria-labelledby="features-title"><div className="section-intro"><p className="product-kicker">FROM RESEARCH TO A WORKING SERVICE</p><h2 id="features-title">Focus on your model.<br />Bring the rest together.</h2></div><div className="feature-grid">{[
      ["01", "Inspect your project", "Point Studio at your model project. Review detected files and configuration without loading weights or importing your code."],
      ["02", "Get your starter kit", "Export an infrastructure kit and a plan for the capabilities your project may need. Inspection is a starting point, not a compatibility certificate."],
      ["03", "Run and evaluate locally", "Use a supported recipe, connect a local server or integrate a reviewed Python adapter. Inspect health, logs, evaluation results and recovery."],
      ["04", "Delegate operations later", "The proposed $20/month service would have Furnace operate the serving infrastructure. Hosting, billing and service commitments are not available yet."],
    ].map(([number,title,text])=><article key={number}><span>{number}</span><h3>{title}</h3><p>{text}</p></article>)}</div></section>
    <section className="comparison" aria-labelledby="plans-title"><p className="product-kicker">ONE PRODUCT, TWO STAGES</p><h2 id="plans-title">Start free.<br />Managed infrastructure is next.</h2><div className="comparison-scroll" role="region" aria-label="Current and proposed Furnace offerings" tabIndex={0}><table><thead><tr><th scope="col">Offering</th><th scope="col">What it includes</th><th scope="col">Availability</th></tr></thead><tbody><tr><th scope="row">Free starter kit + Studio</th><td>Project inspection, kit export and existing local serving, evaluation, logs and recovery tools. You supply the machine.</td><td>Working local preview. Docker is needed for execution; supported recipes and adapter contracts apply.</td></tr><tr><th scope="row">$20/month · proposed</th><td>Furnace-operated serving, security controls, evaluations, monitoring, logs and recovery.</td><td>Planned demo service for one or two supported models before funding. No checkout or hosted provisioning.</td></tr></tbody></table></div><Link prefetch={false} href="/pricing">See what is available and what is planned →</Link></section>
    <section className="product-features scenarios" aria-labelledby="uses-title"><div className="section-intro"><p className="product-kicker">A SMALL, REAL DEMONSTRATION</p><h2 id="uses-title">Prove the infrastructure.<br />Then expand support.</h2><p>Begin with one or two supported demo models. New architectures need a compatible server or adapter and their own validation.</p></div><div className="scenario-grid">{[
      ["Researcher workflow", "Inspect a project, export a kit, connect a model and inspect the evidence around its execution."],
      ["Operational evidence", "Separate completed evaluations, incorrect answers, interrupted runs and actual recovery observations."],
      ["Example application", "The document assistant demonstrates a workload on the infrastructure. It is an example, not Furnace’s primary product."],
    ].map(([title,text])=><article key={title}><h3>{title}</h3><p>{text}</p></article>)}</div><p><Link prefetch={false} href="/examples/documents">Explore the document example →</Link></p></section>
    <section className="product-next"><p className="product-kicker">BUILD THE MODEL. KNOW HOW IT RUNS.</p><h2>Your model deserves more<br />than a loose set of scripts.</h2><p>Start with the free local workflow. Keep preparation and execution explicit, inspect results, and review what your architecture needs next.</p><div><Link prefetch={false} className="product-secondary" href="/start">Get started with your model →</Link><Link prefetch={false} href="/security">Understand the security boundary →</Link><Link prefetch={false} href="/researchers">Compatibility and evidence →</Link></div></section>
  </ProductShell>;
}

export function DocPage({ title, eyebrow = "FURNACE GUIDE", children }: { title: string; eyebrow?: string; children: React.ReactNode }) {
  return <ProductShell><article className="product-doc"><p className="product-kicker">{eyebrow}</p><h1>{title}</h1>{children}</article></ProductShell>;
}
