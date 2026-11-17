import { RECORDED_ONLY } from "@/lib/site";
import { AppHeader } from "@/components/ui/app-header";

/** Navigation fallback; recorded builds must not imply a live evaluation or API request. */
export default function Loading() {
  return (
    <div className="flex min-h-full flex-col">
      <AppHeader />
      <main className="mx-auto w-full max-w-[1200px] flex-1 px-4 py-14 sm:px-6" aria-busy="true">
        <p role="status" className="num flex items-center gap-2 text-[12px] text-fg-2">
          <span aria-hidden="true" className="caret h-2 w-2 rounded-full bg-ember" />
          {RECORDED_ONLY ? "Loading recorded evidence… No live evaluation is running." : "Loading evaluation results…"}
        </p>
        <div aria-hidden="true" className="mt-10 grid gap-6 lg:grid-cols-12">
          <div className="space-y-4 lg:col-span-5">
            <div className="h-3 w-40 rounded bg-bg-2" />
            <div className="h-10 w-full rounded bg-bg-2" />
            <div className="h-10 w-4/5 rounded bg-bg-2" />
            <div className="h-20 w-full rounded bg-bg-1" />
          </div>
          <div className="h-[420px] rounded-[6px] border border-line bg-bg-1 lg:col-span-7" />
        </div>
      </main>
    </div>
  );
}
