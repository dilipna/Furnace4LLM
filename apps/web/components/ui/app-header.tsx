import Link from "next/link";
import { Wordmark } from "@/components/ui/wordmark";

const NAV = [
  ["/guard", "Guard"],
  ["/lab", "Inference Lab"],
  ["/evals", "Evaluations"],
  ["/bench", "Evidence"],
] as const;

// Narrow screens keep the two links a first-time visitor needs; the footer links every page.
const HIDE: Record<string, string> = { "/lab": "hidden sm:inline", "/evals": "hidden md:inline" };

/** Shared top bar. `active` is the href of the current section, highlighted in fg-0. */
export function AppHeader({ active, right }: { active?: string; right?: React.ReactNode }) {
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-bg-0/90 backdrop-blur-sm">
      <div className="mx-auto flex h-14 w-full max-w-[1280px] items-center justify-between gap-4 px-4 sm:px-6">
        <Link href="/" aria-label="Furnace home" className="shrink-0">
          <Wordmark />
        </Link>
        <nav aria-label="Main" className="flex min-w-0 items-center gap-4 text-[13px] text-fg-2 sm:gap-5">
          <div className="flex min-w-0 items-center gap-4 overflow-x-auto sm:gap-5">
            {NAV.map(([href, label]) => (
              <Link
                key={href}
                href={href}
                aria-current={active === href ? "page" : undefined}
                className={`whitespace-nowrap hover:text-fg-0 ${active === href ? "text-fg-0" : ""} ${HIDE[href] ?? ""}`}
              >
                {label}
              </Link>
            ))}
            {right}
          </div>
          <Link
            href="/pilot"
            aria-current={active === "/pilot" ? "page" : undefined}
            className="shrink-0 rounded-[3px] border border-ember/70 px-3 py-1.5 text-[12.5px] whitespace-nowrap text-fg-0 transition-colors duration-150 hover:bg-ember hover:text-bg-0"
          >
            Pilot
          </Link>
        </nav>
      </div>
    </header>
  );
}
