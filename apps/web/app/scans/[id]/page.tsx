import Link from "next/link";
import { notFound } from "next/navigation";
import { Recommendations } from "@/components/blueprint/recommendations";
import { SystemPanel } from "@/components/blueprint/system-panel";
import { ScanLive, ScanLog } from "@/components/scan/scan-live";
import { AppHeader } from "@/components/ui/app-header";
import { ApiError, apiGet } from "@/lib/api";
import type { Blueprint, ScanInfo } from "@/lib/types";

export const dynamic = "force-dynamic";

// Source languages Furnace does not analyze yet (configs and docs are read for every repo).
const UNANALYZED = ["typescript", "javascript", "go", "java", "rust", "csharp", "ruby", "php", "kotlin", "swift"];

/** What the scan could read: Python code is analyzed; other source languages are not (yet). */
function Coverage({ languages, nodes, findings }: { languages: Record<string, number>; nodes: number; findings: number }) {
  const py = languages.python ?? 0;
  const other = Object.entries(languages)
    .filter(([l]) => UNANALYZED.includes(l))
    .sort((a, b) => b[1] - a[1]);
  const otherFiles = other.reduce((a, [, n]) => a + n, 0);
  if (!otherFiles && findings > 0) return null;
  const share = otherFiles / Math.max(1, otherFiles + py);
  return (
    <section aria-label="Scan coverage" className="mt-6 rounded-[6px] border border-line-strong bg-bg-1 px-5 py-4 text-[13px]">
      <h2 className="font-medium text-fg-0">What this scan could read</h2>
      <p className="mt-1 text-fg-2">
        Furnace analyzes <b className="text-fg-1">Python</b> code today ({py} file{py === 1 ? "" : "s"} here)
        {otherFiles > 0 && (
          <>
            ; this repository is {Math.round(share * 100)}% {other.map(([l, n]) => `${l} (${n})`).join(", ")}, which was
            not analyzed (configs, dependencies and docs were). LLM calls, prompts and routes written in those languages
            are not in this Blueprint.
          </>
        )}
        {otherFiles === 0 && "."}
      </p>
      {findings === 0 && (
        <p className="mt-2 text-fg-2">
          {nodes === 0
            ? "No LLM application structure was found in the analyzed code, so there are no findings: that is a coverage limit, not a clean bill of health."
            : "No findings for the analyzed code."}
        </p>
      )}
    </section>
  );
}

function Stat({ label, value }: { label: string; value: unknown }) {
  return (
    <div>
      <div className="text-[11px] text-fg-3">{label}</div>
      <div className="num text-[15px] text-fg-0">{String(value ?? "–")}</div>
    </div>
  );
}

export default async function ScanPage({ params }: PageProps<"/scans/[id]">) {
  const { id } = await params;
  let scan: ScanInfo;
  try {
    scan = await apiGet<ScanInfo>(`/api/scans/${id}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
  const bp = scan.status === "succeeded" ? await apiGet<Blueprint>(`/api/scans/${id}/blueprint`) : null;
  const s = scan.stats;

  return (
    <div className="flex min-h-full flex-col">
      <AppHeader
        right={
          <span className="num border-l border-line pl-5 text-[12px] text-fg-3">scan {scan.id.slice(0, 8)}</span>
        }
      />

      <main className="mx-auto w-full max-w-[1280px] flex-1 px-4 py-8 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-6 border-b border-line pb-6">
          <div>
            <p className="text-[12px] text-fg-3">Reliability + Inference Blueprint</p>
            <h1 className="mt-1 font-display text-[28px] font-semibold tracking-[-0.02em]">{scan.repo ?? scan.project}</h1>
            <p className="num mt-1 text-[12px] text-fg-2">
              {scan.commit_sha ? `@ ${scan.commit_sha.slice(0, 10)}` : s.fixture ? "local fixture" : "uploaded source"} · {scan.status}
            </p>
          </div>
          {bp && (
            <div className="flex flex-wrap items-end gap-x-8 gap-y-3">
              {Number(s.nodes ?? 0) > 0 && (
                <Link href={`/scans/${scan.id}/graph`} className="text-[13px] text-fg-1 hover:text-fg-0 hover:underline">
                  Graph →
                </Link>
              )}
              <Stat label="files" value={s.files} />
              <Stat label="evidence" value={s.facts} />
              <Stat label="claims" value={s.claims} />
              <Stat label="graph" value={`${s.nodes}/${s.edges}`} />
              <Stat label="findings" value={s.recommendations} />
            </div>
          )}
        </div>

        {!bp && scan.status !== "failed" && (
          <div className="mt-8 max-w-[860px]">
            <ScanLive scanId={scan.id} />
          </div>
        )}
        {scan.status === "failed" && (
          <p role="alert" className="mt-8 text-[13px] text-bad">
            {scan.error ?? "The scan failed."}
          </p>
        )}
        {bp && (
          <Coverage
            languages={(s.languages as Record<string, number> | undefined) ?? {}}
            nodes={Number(s.nodes ?? 0)}
            findings={bp.recommendations.length}
          />
        )}
        {bp && <ScanLog scanId={scan.id} />}
        {bp && (
          <div className="mt-8 grid gap-10 lg:grid-cols-[minmax(0,1fr)_380px]">
            <Recommendations recs={bp.recommendations} evidence={bp.evidence} />
            <aside className="lg:sticky lg:top-6 lg:self-start">
              <SystemPanel spec={bp.appspec} />
            </aside>
          </div>
        )}
      </main>
    </div>
  );
}
