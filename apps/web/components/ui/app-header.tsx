import Link from "next/link";
import { Wordmark } from "@/components/ui/wordmark";

const NAV: [string, string][] = [
  ["/", "Home"],
  ["/start", "Get started"],
  ["/demo", "Examples"],
];
const TOOLS: [string, string][] = [
  ["/research", "Technical research"],
  ["/prefix-check", "Prefix checker"],
  ["/guard", "Guard"],
  ["/lab", "Inference Lab"],
  ["/evals", "Evaluations"],
  ["/bench", "Evidence"],
];
/** Shared top bar. `active` is the href of the current section, highlighted in fg-0. */
export function AppHeader({
  active,
  right,
}: {
  active?: string;
  right?: React.ReactNode;
  variant?: "app" | "marketing";
}) {
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-bg-0/90 backdrop-blur-sm">
      <div className="mx-auto flex min-h-14 w-full max-w-[1280px] flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
        <Link href="/" aria-label="Furnace home" className="shrink-0">
          <Wordmark />
        </Link>
        <nav aria-label="Main" className="flex min-w-0 items-center gap-4 text-[13px] text-fg-2 sm:gap-5">
          <div className="flex min-w-0 flex-wrap items-center gap-3 sm:gap-5">
            {NAV.map(([href, label]) => (
              <Link
                key={href}
                href={href}
                aria-current={active === href ? "page" : undefined}
                className={`whitespace-nowrap hover:text-fg-0 ${active === href ? "text-fg-0" : ""} ${href === "/" ? "hidden sm:inline" : ""}`}
              >
                {label}
              </Link>
            ))}
            <details key={active ?? "home"} className="relative shrink-0">
              <summary className="cursor-pointer list-none rounded px-1 py-1">More <span aria-hidden="true">⌄</span></summary>
              <div className="absolute right-0 top-full z-30 mt-3 grid w-52 gap-1 rounded-xl border border-line bg-bg-1 p-2 shadow-lg">
                {TOOLS.map(([href, label]) => (
                  <Link key={href} href={href} aria-current={active === href ? "page" : undefined}
                    className="rounded-lg px-3 py-2 hover:bg-bg-2 hover:text-fg-0">{label}</Link>
                ))}
                <Link href="/pricing" className="rounded-lg px-3 py-2 hover:bg-bg-2 hover:text-fg-0">Plans</Link>
              </div>
            </details>
            {right}
          </div>
          <Link
            href="/pilot"
            aria-current={active === "/pilot" ? "page" : undefined}
            className="shrink-0 rounded-full bg-ember px-4 py-1.5 text-[12.5px] font-medium whitespace-nowrap text-bg-0 transition-colors duration-150 hover:bg-ember-hi"
          >
            <span>Help</span>
          </Link>
        </nav>
      </div>
    </header>
  );
}
