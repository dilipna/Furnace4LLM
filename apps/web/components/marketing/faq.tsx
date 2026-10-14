import type { Story } from "@/lib/story";

const REPO = "https://github.com/dilipna/Furnace4LLM/blob/main";

function A({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a href={href} className="underline decoration-line-strong underline-offset-2 hover:text-fg-0">
      {children}
    </a>
  );
}

/** Questions a technical buyer or an investor asks, answered with the limits included. */
export function Faq({ s }: { s: Story | null }) {
  const g = s?.gate;
  const items: [string, React.ReactNode][] = [
    [
      "Doesn’t my eval tool already measure latency?",
      <>
        Often, yes. <A href="https://www.promptfoo.dev/docs/configuration/expected-outputs/deterministic/">promptfoo</A> can
        fail a test above a per-call latency threshold, and <A href="https://reference.langchain.com/python/langsmith/schemas/ExperimentRunStats/first_token_p99">LangSmith</A>{" "}
        records first-token percentiles. Furnace is narrower. It compares two revisions on your own server in interleaved
        runs, decides with an interval instead of a fixed threshold, reads the server’s cache hit rate, points to the
        line that changed, and for one kind of regression drafts a fix. It does not judge answer quality, so keep your
        eval tool for that.
      </>,
    ],
    [
      "How do you know the gate isn’t just GPU noise?",
      g ? (
        <>
          The decision rule was frozen before it was validated. On unchanged code it raised {g.falseAlarms} false alarms in{" "}
          {g.n} trials. It blocked the known cache regression in {g.blocks} of {g.blockN}. It is not perfect: smaller
          slowdowns were left inconclusive in {g.undecided} of {g.gradedN} trials, so catching regressions just above the
          10% tolerance is not shown. <A href={`${REPO}/bench/results/${g.campaign}/validation/report.md`}>Validation report</A>
        </>
      ) : (
        <>
          The decision rule was frozen before validation; the results are in the <A href={`${REPO}/docs/claims.md`}>claims ledger</A>.
        </>
      ),
    ],
    [
      "What works today, and what doesn’t?",
      <>
        It works for Python apps that build prompts in code and call a model you serve (measured on vLLM). It needs a
        runner on a machine with Docker and a GPU. It can repair one regression family: per-request values at the start
        of a prompt. Not yet: TypeScript, latency on hosted APIs, and other repairs, which it refuses rather than guesses.
        The GitHub App path has passed tests against a mock GitHub; the first run on real GitHub is in progress.
      </>,
    ],
    [
      "Where does my code run?",
      <>
        On your machine. The runner downloads your repository with a token scoped to that one repository and runs your
        tests in a container with no network, read-only, without root. Prompts go only to your own model server.{" "}
        <A href={`${REPO}/docs/security.md`}>Security controls and their tests</A>
      </>,
    ],
    [
      "Is anyone using it?",
      <>
        Not yet. Furnace is an early prototype, verified on two fixture apps on one laptop GPU. We are looking for a few
        design partners who serve their own models to try it on one repository, for free.
      </>,
    ],
    [
      "How would it make money?",
      <>
        This is untested. The leading idea is a per-repository subscription for the hosted control plane, with the runner
        on the customer’s own hardware. The pilots exist partly to learn whether teams would pay, and for what.
      </>,
    ],
  ];
  return (
    <div className="divide-y divide-line border-y border-line">
      {items.map(([q, a]) => (
        <details key={q} className="group py-5">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-6 text-[16px] font-medium text-fg-0 select-none">
            {q}
            <span aria-hidden="true" className="num shrink-0 text-[18px] text-ember transition-transform duration-200 group-open:rotate-45">
              +
            </span>
          </summary>
          <p className="mt-3 max-w-[760px] text-[14px] leading-relaxed text-fg-2">{a}</p>
        </details>
      ))}
    </div>
  );
}
