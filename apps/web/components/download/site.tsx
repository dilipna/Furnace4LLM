"use client";
import Image from "next/image";

import Link from "next/link";
import { useState, useSyncExternalStore } from "react";
import { platformFor, type Installer } from "@/lib/download";
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
    <footer className="product-footer"><div><Link prefetch={false} href="/" className="product-logo"><span aria-hidden="true">F</span> Furnace</Link><p>A home for your local model.</p><small>Local application preview · no account required</small></div>
      <div><strong>Product</strong><Link prefetch={false} href="/start">Getting started</Link><Link prefetch={false} href="/releases">Releases & checksums</Link><Link prefetch={false} href="/faq">FAQ</Link></div>
      <div><strong>Project</strong><Link prefetch={false} href="/about">About</Link><Link prefetch={false} href="/security">Security</Link><a href={repo}>Source on GitHub ↗</a><Link prefetch={false} href="/earlier-work">Earlier work</Link></div>
      <div><strong>Policies</strong><Link prefetch={false} href="/privacy">Privacy policy · draft</Link><Link prefetch={false} href="/terms">Terms · draft</Link><Link prefetch={false} href="/support">Contact & support</Link></div>
    </footer>
  </div>;
}

export function DownloadButton({ installer }: { installer: Installer | null }) {
  const platform = useSyncExternalStore(subscribe, () => platformFor(navigator.userAgent), () => "windows" as const);
  const windows = platform === "windows";
  return <div className="download-block" id="download">
    {installer ? <a className="download-primary" href={windows ? "/downloads/" + installer.file : "#platforms"} download={windows || undefined} onClick={windows ? undefined : () => document.getElementById("platforms")?.setAttribute("open", "")}>{windows ? "Download Furnace" : "See download options"}<span aria-hidden="true">↓</span></a>
      : <Link prefetch={false} className="download-primary" href="/releases">Installer build status <span aria-hidden="true">→</span></Link>}
    <p className="download-caption">{installer ? `Windows x64 · ${installer.version} · ${(installer.bytes / 1048576).toFixed(1)} MiB · ${installer.signed ? "Signed" : "Unsigned preview"}` : "Windows installer preview · no public release yet"}</p>
    {installer && <details className="checksum"><summary>Version, build date & SHA-256</summary><dl><dt>Version</dt><dd>{installer.version}</dd><dt>Built (UTC)</dt><dd>{installer.built_at}</dd><dt>Source</dt><dd>{installer.commit}</dd><dt>SHA-256</dt><dd data-testid="checksum">{installer.sha256}</dd></dl><Link prefetch={false} href="/releases">How to verify this download →</Link></details>}
    <details className="platform-options" id="platforms"><summary>Other platforms & requirements</summary>{installer && <p><a href={"/downloads/" + installer.file} download>Download for Windows x64</a></p>}<p>Windows x64 is the installer target. Model runs have been recorded on Windows 11 with Docker Desktop. CPU works; NVIDIA is optional.</p><p>macOS and Linux: installer previews not built or verified. <a href={repo + "/blob/main/docs/operations/release-procedure.md"}>Source-based setup ↗</a></p><p>No fixed universal RAM/disk promise: choose a recipe and review its memory, image and weight sizes. <Link prefetch={false} href="/start">See requirements.</Link></p></details>
  </div>;
}

export function ProductHome({ installer }: { installer: Installer | null }) {
  return <ProductShell><section className="product-hero"><div className="product-kicker"><span /> Free local app · Windows preview</div><h1>Your model.<br /><em>Your machine.</em></h1><p className="product-lede">Run open-weight models with isolated serving,<br className="desktop-break" /> evaluations, logs and crash recovery.</p><DownloadButton installer={installer} /><p className="hero-note">Install. Open. Bring your model to life.<br />Docker is needed for model execution, not for exploring Studio.</p></section>
    <section className="studio-window" aria-label="Studio preview"><div className="window-bar"><span aria-hidden="true">● ● ●</span><span>Furnace Studio · your local workspace</span><span>127.0.0.1</span></div><Image unoptimized src="/product/studio-home.png" alt="Actual installed Furnace Studio workspace. No model is running in this capture." width="1440" height="960" /><p>Recorded installed-app capture · metadata only, not model inference. <Link prefetch={false} href="/demo">Explore the tour →</Link></p></section>
    <section className="product-features" aria-labelledby="features-title"><div className="section-intro"><p className="product-kicker">THE INFRASTRUCTURE AROUND YOUR MODEL</p><h2 id="features-title">Less setup between<br />an idea and a working service.</h2></div><div className="feature-grid">{[
      ["01", "A place to run", "Prepare pinned weights, then start a resource-limited model container. Downloads and execution stay under your control."],
      ["02", "Know what passed", "Evaluate saved cases with clear scoring rules. Keep failed and unscored outcomes alongside the passes."],
      ["03", "Pick up after a failure", "See health and operational logs. Restart explicitly, retain interrupted attempts and compare completed results."],
      ["04", "Keep your work local", "Studio has no accounts or telemetry. Cases, results and exports stay on your machine. Preparation downloads public assets."],
    ].map(([number, title, text]) => <article key={number}><span>{number}</span><h3>{title}</h3><p>{text}</p></article>)}</div></section>
    <section className="product-next"><p className="product-kicker">A SMALL, HONEST START</p><h2>Qwen first. Your next idea after that.</h2><p>Qwen2.5-0.5B and Granite-4.0-H-350M have recorded CPU and NVIDIA journeys. Granite is a Mamba-2 hybrid. Supported recipes are deliberate; arbitrary architecture compatibility is not assumed.</p><div><Link prefetch={false} className="product-secondary" href="/start">Get started →</Link><a href={repo + "/blob/main/docs/product/real-model-validation.md"}>Read the actual results ↗</a></div></section>
  </ProductShell>;
}

export function DocPage({ title, eyebrow = "FURNACE GUIDE", children }: { title: string; eyebrow?: string; children: React.ReactNode }) {
  return <ProductShell><article className="product-doc"><p className="product-kicker">{eyebrow}</p><h1>{title}</h1>{children}</article></ProductShell>;
}
