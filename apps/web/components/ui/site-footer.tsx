import Link from "next/link";
import { Wordmark } from "@/components/ui/wordmark";

const REPO = "https://github.com/dilipna/Furnace4LLM";

const COLS: [string, [string, string][]][] = [
  ["Product", [["/pilot", "Pilot setup"], ["/guard", "Guard runs"], ["/lab", "Inference Lab"]]],
  ["Evidence", [["/bench", "FurnaceBench"], ["/evals", "Evaluations"], [`${REPO}/blob/main/docs/claims.md`, "Claims ledger"], [`${REPO}/blob/main/docs/completion.md`, "Acceptance checklist"]]],
  ["Source", [[REPO, "GitHub repository"], [`${REPO}/blob/main/docs/security.md`, "Security controls"], [`${REPO}/blob/main/docs/architecture.md`, "Architecture"]]],
];

export function SiteFooter() {
  return (
    <footer className="border-t border-line bg-bg-1">
      <div className="mx-auto grid w-full max-w-[1200px] gap-10 px-4 py-12 sm:px-6 md:grid-cols-[1.4fr_repeat(3,1fr)]">
        <div>
          <Wordmark />
          <p className="mt-4 max-w-[300px] text-[12px] leading-relaxed text-fg-3">
            An early-stage project. Results come from fixture apps on one laptop GPU; the live GitHub run and the hosted
            pilot are not done yet.
          </p>
        </div>
        {COLS.map(([title, links]) => (
          <div key={title}>
            <h2 className="text-[11.5px] tracking-wide text-fg-3 uppercase">{title}</h2>
            <ul className="mt-3 space-y-2 text-[13px]">
              {links.map(([href, label]) => (
                <li key={href}>
                  {href.startsWith("/") ? (
                    <Link href={href} className="text-fg-2 hover:text-fg-0">
                      {label}
                    </Link>
                  ) : (
                    <a href={href} className="text-fg-2 hover:text-fg-0">
                      {label}
                    </a>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </footer>
  );
}
