import Link from "next/link";
import { notFound } from "next/navigation";
import { Recommendations } from "@/components/blueprint/recommendations";
import { SystemPanel } from "@/components/blueprint/system-panel";
import { ScanLive } from "@/components/scan/scan-live";
import { Wordmark } from "@/components/ui/wordmark";
import { ApiError, apiGet } from "@/lib/api";
import type { Blueprint, ScanInfo } from "@/lib/types";

export const dynamic = "force-dynamic";

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
      <header className="border-b border-line">
        <div className="mx-auto flex h-14 w-full max-w-[1280px] items-center justify-between px-4 sm:px-6">
          <Link href="/">
            <Wordmark />
          </Link>
          <span className="num text-[12px] text-fg-3">scan {scan.id.slice(0, 8)}</span>
        </div>
      </header>

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
            <div className="flex gap-8">
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
