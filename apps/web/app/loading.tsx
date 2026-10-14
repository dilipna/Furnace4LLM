import { AppHeader } from "@/components/ui/app-header";

/** Streamed while a page waits for the results API (a sleeping free-tier API takes about a minute). */
export default function Loading() {
  return (
    <div className="flex min-h-full flex-col">
      <AppHeader />
      <main className="mx-auto w-full max-w-[1200px] flex-1 px-4 py-14 sm:px-6" aria-busy="true">
        <p role="status" className="num flex items-center gap-2 text-[12px] text-fg-2">
          <span aria-hidden="true" className="caret h-2 w-2 rounded-full bg-ember" />
          Loading results from the API… If the hosted API was asleep, this can take up to a minute.
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
