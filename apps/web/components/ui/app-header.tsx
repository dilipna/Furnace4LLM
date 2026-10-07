import Link from "next/link";
import { Wordmark } from "@/components/ui/wordmark";

const NAV = [
  ["/lab", "Inference Lab"],
  ["/guard", "Guard"],
  ["/evals", "Evaluations"],
  ["/bench", "FurnaceBench"],
  ["/pricing", "Pricing"],
] as const;

/** Shared top bar. `active` is the href of the current section, highlighted in fg-0. */
export function AppHeader({ active, right }: { active?: string; right?: React.ReactNode }) {
  return (
    <header className="border-b border-line">
      <div className="mx-auto flex h-14 w-full max-w-[1280px] items-center justify-between gap-6 px-4 sm:px-6">
        <Link href="/" aria-label="Furnace home">
          <Wordmark />
        </Link>
        <nav aria-label="Main" className="flex items-center gap-5 overflow-x-auto text-[13px] text-fg-2">
          {NAV.map(([href, label]) => (
            <Link
              key={href}
              href={href}
              aria-current={active === href ? "page" : undefined}
              className={`whitespace-nowrap hover:text-fg-0 ${active === href ? "text-fg-0" : ""}`}
            >
              {label}
            </Link>
          ))}
          {right}
        </nav>
      </div>
    </header>
  );
}
