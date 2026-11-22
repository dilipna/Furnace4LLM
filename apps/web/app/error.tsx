"use client";

import { RECORDED_ONLY } from "@/lib/site";
import Link from "next/link";
import { useEffect } from "react";
import { Wordmark } from "@/components/ui/wordmark";

const REPO = "https://github.com/dilipna/Furnace4LLM/blob/main";

/** Shown when a page could not be rendered, most often because the results API did not answer. */
export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.warn("page failed to render:", error.digest ?? error.message);
  }, [error]);
  return (
    <div className="flex min-h-full flex-col">
      <header className="border-b border-line">
        <div className="mx-auto flex h-14 w-full max-w-[1280px] items-center px-4 sm:px-6">
          <Link href="/" aria-label="Furnace home">
            <Wordmark />
          </Link>
        </div>
      </header>
      <main className="mx-auto w-full max-w-[720px] flex-1 px-4 py-20 sm:px-6">
        <p className="num text-[11.5px] tracking-[0.08em] text-ember uppercase">Page unavailable</p>
        <h1 className="mt-3 font-display text-[30px] leading-tight font-semibold tracking-[-0.02em]">
          This page could not load its data.
        </h1>
        <p className="mt-4 text-[14px] leading-relaxed text-fg-2">
          {RECORDED_ONLY
            ? "The recorded page could not be displayed. No live evaluation is running. Try again or read the evidence files below."
            : "The page could not display evaluation results. Check the API and runner logs, then try again."}
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <button
            onClick={reset}
            className="inline-flex h-10 items-center rounded-[3px] bg-ember px-5 text-[14px] font-medium text-bg-0 transition-colors duration-150 hover:bg-ember-hi"
          >
            Try again
          </button>
          <Link
            href="/pilot"
            className="inline-flex h-10 items-center rounded-[3px] border border-line-strong px-5 text-[14px] text-fg-0 hover:bg-bg-2"
          >
            Pilot setup (static page)
          </Link>
        </div>
        <p className="mt-10 text-[13px] text-fg-3">
          The same results are in the repository as files:{" "}
          <a className="underline decoration-line-strong underline-offset-2 hover:text-fg-1" href={`${REPO}/docs/claims.md`}>
            claims ledger
          </a>{" "}
          ·{" "}
          <a className="underline decoration-line-strong underline-offset-2 hover:text-fg-1" href={`${REPO}/docs/demo-3min.md`}>
            demo script
          </a>
          {error.digest ? <span className="num"> · ref {error.digest}</span> : null}
        </p>
      </main>
    </div>
  );
}
