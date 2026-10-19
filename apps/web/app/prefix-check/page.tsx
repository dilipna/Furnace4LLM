import type { Metadata } from "next";
import { AppHeader } from "@/components/ui/app-header";
import { SiteFooter } from "@/components/ui/site-footer";
import { PrefixChecker } from "@/components/marketing/prefix-checker";

export const metadata: Metadata = {
  title: "Prompt prefix checker · Furnace",
  description: "Compare rendered base/head prompts in your browser. No upload, account, or GPU required.",
};

export default function PrefixCheckPage() {
  return <><AppHeader active="/prefix-check" /><main className="mx-auto min-h-[75vh] max-w-[1100px] px-4 py-12 sm:px-6">
    <p className="font-mono text-xs tracking-widest text-ember">USE FURNACE / NO GPU REQUIRED</p>
    <h1 className="mt-4 text-4xl font-semibold tracking-tight sm:text-5xl">Check your prompt prefix.</h1>
    <p className="mt-5 max-w-3xl text-base leading-relaxed text-fg-2">See whether a prompt edit shortens the stable prefix shared across requests. Start with an example, then compare your own rendered prompts.</p>
    <p className="mt-5 rounded-lg border border-line bg-bg-1 p-4 text-sm leading-relaxed"><strong>Private by design.</strong> Comparison runs in your browser. Prompt text is not uploaded, saved by Furnace, or sent to a model. Clear prompts when finished; browser extensions may have their own access.</p>
    <PrefixChecker />
    <aside className="mt-10 border-t border-line pt-6 text-sm leading-relaxed text-fg-2">
      <h2 className="font-semibold text-fg-0">What this check can tell you</h2>
      <p className="mt-2">This uses Forge’s text serialization (role, newline, content, newline) and a threshold of 90% of the base prefix, rounded down. Counts are Unicode characters, not tokens. It cannot detect disabled server caching, measure latency, or evaluate answer quality. A structural PASS is possible with caching turned off.</p>
      <p className="mt-3">For measured performance, <a className="text-ember underline" href="https://github.com/dilipna/Furnace4LLM/tree/main/experiments/prefix-cache">use the reproducible runner and study instructions</a>. The public website does not run GPU benchmarks or scan repositories.</p>
    </aside>
  </main><SiteFooter /></>;
}
