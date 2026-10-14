import Link from "next/link";
import { AppHeader } from "@/components/ui/app-header";

export default function NotFound() {
  return (
    <div className="flex min-h-full flex-col">
      <AppHeader />
      <main className="mx-auto w-full max-w-[720px] flex-1 px-4 py-20 sm:px-6">
        <p className="num text-[11.5px] tracking-[0.08em] text-ember uppercase">404</p>
        <h1 className="mt-3 font-display text-[30px] font-semibold tracking-[-0.02em]">Nothing here.</h1>
        <p className="mt-4 text-[14px] leading-relaxed text-fg-2">
          The link may point to a scan or run that this deployment does not have. Scans and Guard runs are stored per
          deployment, so a link from a local demo does not open on the hosted site.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/" className="inline-flex h-10 items-center rounded-[3px] bg-ember px-5 text-[14px] font-medium text-bg-0 hover:bg-ember-hi">
            Home
          </Link>
          <Link href="/guard/r1_dynamic_head" className="inline-flex h-10 items-center rounded-[3px] border border-line-strong px-5 text-[14px] text-fg-0 hover:bg-bg-2">
            The recorded R1 run
          </Link>
        </div>
      </main>
    </div>
  );
}
