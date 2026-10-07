import Link from "next/link";
import { notFound } from "next/navigation";
import { type GEdge, type GNode, GraphView } from "@/components/graph/graph-view";
import { AppHeader } from "@/components/ui/app-header";
import { ApiError, apiGet } from "@/lib/api";
import type { ScanInfo } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function GraphPage({ params }: PageProps<"/scans/[id]/graph">) {
  const { id } = await params;
  let scan: ScanInfo;
  try {
    scan = await apiGet<ScanInfo>(`/api/scans/${id}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
  const g = scan.status === "succeeded" ? await apiGet<{ nodes: GNode[]; edges: GEdge[] }>(`/api/scans/${id}/graph`) : null;

  return (
    <div className="flex min-h-full flex-col">
      <AppHeader />
      <main className="mx-auto w-full max-w-[1500px] flex-1 px-4 py-8 sm:px-6">
        <Link href={`/scans/${id}`} className="text-[12px] text-fg-3 hover:text-fg-1">
          ← Blueprint
        </Link>
        <h1 className="mt-2 font-display text-[24px] font-semibold tracking-[-0.02em]">
          Behavior-to-code graph <span className="text-fg-3">· {scan.repo ?? scan.project}</span>
        </h1>
        <p className="mt-1 mb-6 text-[12px] text-fg-3">
          {g ? `${g.nodes.length} nodes, ${g.edges.length} edges` : "The scan has not finished."} Every node and edge is
          derived from evidence in the repository.
        </p>
        {g && <GraphView nodes={g.nodes} edges={g.edges} />}
      </main>
    </div>
  );
}
