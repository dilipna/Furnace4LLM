import { AppHeader } from "@/components/ui/app-header";
import { Markdown } from "@/components/ui/markdown";
import { apiGet } from "@/lib/api";
import { type Campaign, campaigns } from "@/lib/bench";

export const dynamic = "force-dynamic";

export default async function BenchPage({ searchParams }: PageProps<"/bench">) {
  const sp = await searchParams;
  const list = (await campaigns()).filter((c) => c.has_report);
  const wanted = typeof sp.c === "string" ? sp.c : undefined;
  const chosen: Campaign | undefined = list.find((c) => c.name === wanted) ?? list[0];
  const data = chosen
    ? await apiGet<{ report_md: string | null; notes_md: string | null }>(`/api/bench/campaigns/${chosen.name}`)
    : null;

  return (
    <div className="flex min-h-full flex-col">
      <AppHeader active="/bench" />
      <main className="mx-auto w-full max-w-[1100px] flex-1 px-4 py-8 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-4 border-b border-line pb-6">
          <div>
            <p className="text-[12px] text-fg-3">FurnaceBench</p>
            <h1 className="mt-1 font-display text-[28px] font-semibold tracking-[-0.02em]">How well does Furnace work?</h1>
            <p className="mt-2 max-w-[700px] text-[13px] text-fg-2">
              Five research questions, measured with reproducible commands and reported with their negative results. The
              report below is generated from result files only (<span className="num">uv run poe bench-report</span>).
            </p>
          </div>
          {list.length > 1 && (
            <nav aria-label="Campaigns" className="flex gap-2 text-[12px]">
              {list.map((c) => (
                <a
                  key={c.name}
                  href={`/bench?c=${c.name}`}
                  aria-current={c.name === chosen?.name ? "page" : undefined}
                  className={`num rounded-[3px] border px-2 py-1 ${c.name === chosen?.name ? "border-line-strong text-fg-0" : "border-line text-fg-2"}`}
                >
                  {c.name}
                </a>
              ))}
            </nav>
          )}
        </div>
        {data?.notes_md && (
          <details className="mt-6 rounded-[6px] border border-line bg-bg-1 px-5 py-3">
            <summary className="cursor-pointer text-[13px] text-fg-1">Campaign conditions (read first)</summary>
            <Markdown source={data.notes_md} />
          </details>
        )}
        {data?.report_md ? (
          <article className="mt-4">
            <Markdown source={data.report_md} />
          </article>
        ) : (
          <p className="mt-8 text-[13px] text-fg-2">No report yet. Run the FurnaceBench commands, then bench-report.</p>
        )}
      </main>
    </div>
  );
}
