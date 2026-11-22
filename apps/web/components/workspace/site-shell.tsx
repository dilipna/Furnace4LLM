"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import s from "./simple-workspace.module.css";

export function SiteShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const links = [
    ["/", "Home", "⌂"],
    ["/start", "Get started", "+"],
    ["/demo", "Recorded example", "▷"],
  ];
  return (
    <div className={s.shell}>
      <a className={s.skip} href="#main">Skip to content</a>
      <header className={s.mobileHeader}>
        <button type="button" aria-label="Toggle navigation" aria-expanded={menuOpen}
          aria-controls="site-navigation" onClick={() => setMenuOpen(!menuOpen)}>☰</button>
        <Link href="/">Furnace</Link><span>Local preview</span>
      </header>
      <aside id="site-navigation" className={`${s.sidebar} ${menuOpen ? s.sidebarOpen : ""}`}>
        <Link href="/" className={s.brand} onClick={() => setMenuOpen(false)}>
          <span className={s.mark} aria-hidden="true">F</span>Furnace
        </Link>
        <nav aria-label="Main navigation">
          {links.map(([href, label, icon]) => (
            <Link key={href} href={href} className={path === href ? s.selected : ""}
              aria-current={path === href ? "page" : undefined} onClick={() => setMenuOpen(false)}>
              <span aria-hidden="true">{icon}</span>{label}
            </Link>
          ))}
        </nav>
        <div className={s.sidebarBottom}>
          <details>
            <summary>More from Furnace</summary>
            <nav aria-label="Research and support">
              <Link href="/research" onClick={() => setMenuOpen(false)}>Technical research</Link>
              <Link href="/bench" onClick={() => setMenuOpen(false)}>Saved evidence</Link>
              <Link href="/pricing" onClick={() => setMenuOpen(false)}>Plans</Link>
              <a href="https://github.com/dilipna/Furnace4LLM">Source code ↗</a>
            </nav>
          </details>
          <Link href="/start#help" onClick={() => setMenuOpen(false)}>Help getting started</Link>
          <p>Free local preview<span>Managed hosting is still in development.</span></p>
        </div>
      </aside>
      <div className={s.content}>
        <div className={s.topbar}>
          <span>A workspace for your model</span>
          <Link href="/start" className={s.topAction}>Get started <span aria-hidden="true">↗</span></Link>
        </div>
        <main id="main" tabIndex={-1}>{children}</main>
      </div>
    </div>
  );
}
