import type { Metadata } from "next";
import Link from "next/link";
import { OutcomeGuide } from "@/components/marketing/outcome-guide";
import { AppHeader } from "@/components/ui/app-header";
import { SiteFooter } from "@/components/ui/site-footer";

export const metadata: Metadata = {
  title: "App fit & first evaluation · Furnace",
  description: "Check Python/vLLM compatibility, prerequisites, permissions and the path to one supervised evaluation.",
};
const REPO = "https://github.com/dilipna/Furnace4LLM/blob/main";
const LINK = "underline underline-offset-4";
const FIT = [
  ["Python prompt-building code", "Furnace must be able to slice the handler without importing arbitrary app code on the host. Some handlers are refused. JavaScript/TypeScript extraction is not supported."],
  ["A team-controlled model server", "The measured path is vLLM with an OpenAI-compatible endpoint and prefix caching. It may run on a remote GPU accessible to your runner. Hosted-provider latency and other server adapters are not validated configurations."],
  ["Git, Python 3.12, uv and Docker", "Use Linux Docker or Docker Desktop. The runner needs enough resources to install the app’s requirements and run tests in disposable containers. GPU inference needs a model server; offline structural proposals do not."],
  ["One authorized GitHub repository", "Choose a disposable test repository or a reviewed same-repository pull request. You need permission to install a GitHub App on it. Fork PR execution is refused."],
];
function Command({ children }: { children: string }) {
  return <pre className="my-4 overflow-x-auto rounded border border-line-strong bg-bg-1 p-4 text-[13px] leading-relaxed"><code>{children}</code></pre>;
}
function Step({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="border-t border-line py-8"><h3 className="font-display text-2xl font-semibold">{title}</h3><div className="mt-4 space-y-4 text-sm leading-relaxed text-fg-2">{children}</div></section>;
}
export default function PilotPage() {
  return (
    <div className="flex min-h-full flex-col">
      <AppHeader variant="marketing" active="/pilot" />
      <a href="#main" className="sr-only focus:not-sr-only focus:p-4">Skip to content</a>
      <main id="main" className="flex-1">
        <div className="mx-auto w-full max-w-[1100px] px-4 pt-12 sm:px-6">
          <p className="num text-xs tracking-widest text-ember uppercase">App fit · supervised first evaluation</p>
          <h1 className="mt-4 max-w-[850px] font-display text-4xl leading-tight font-semibold sm:text-5xl">Can Furnace check your Python AI app?</h1>
          <p className="mt-5 max-w-[800px] text-lg leading-relaxed text-fg-2">Start with one repository, one representative workload and one evaluation. Furnace compares a proposed code change with its original version before you merge. Supported repairs become drafts for your review.</p>
          <p className="mt-5 rounded border border-line-strong p-4 text-sm leading-relaxed text-fg-2">This website shows recorded evidence and a <Link className={LINK} href="/prefix-check">browser-local prompt checker</Link>. It cannot run your jobs or connect to your model server. The CLI and runner are source-available; no production readiness, customer adoption or setup-time guarantee is claimed.</p>
          <nav aria-label="Setup sections" className="my-6 flex flex-wrap gap-5 text-sm"><a className={LINK} href="#fit">1. Check fit</a><a className={LINK} href="#execution">2. Understand execution</a><a className={LINK} href="#first">3. First evaluation</a><a className={LINK} href="#outcomes-h">4. Read outcomes</a><a className={LINK} href="#recovery">5. Recover & stop</a></nav>
          <section id="fit" className="scroll-mt-20 py-8" aria-labelledby="fit-h">
            <h2 id="fit-h" className="font-display text-3xl font-semibold">Check prerequisites before installing</h2>
            <dl className="mt-6 grid gap-4 sm:grid-cols-2">{FIT.map(([title, text]) => <div key={title} className="rounded border border-line-strong p-5"><dt className="font-semibold">{title}</dt><dd className="mt-3 text-sm leading-relaxed text-fg-2">{text}</dd></div>)}</dl>
            <p className="mt-5 text-sm text-fg-2">Also needed: reviewed local suite Python, representative sanitized input questions, and app tests installable from requirements files. General repair and proof of unchanged answers are outside scope. <Link className={LINK} href="/demo">See the recorded workflow first.</Link></p>
          </section>
          <section id="execution" className="scroll-mt-20 py-8" aria-labelledby="execution-h">
            <h2 id="execution-h" className="font-display text-3xl font-semibold">Where execution and data go</h2>
            <ul className="mt-5 space-y-3 text-sm leading-relaxed text-fg-2">
              <li><strong className="text-fg-0">Website:</strong> hosted static recordings. Your prompt-checker text stays in your browser; no evaluation service runs here.</li>
              <li><strong className="text-fg-0">CLI / runner:</strong> your trusted machine downloads source and orchestrates checks. Suite Python and its imports execute on this host: review them first.</li>
              <li><strong className="text-fg-0">Docker sandbox:</strong> app tests execute in disposable copies, as a non-root user with limits and no test-time network. Dependency installation has network access and can run install scripts. A read-only container root does not make the disposable repository copy immutable.</li>
              <li><strong className="text-fg-0">Model server:</strong> your chosen endpoint receives rendered prompts for measured evaluations. Logs and results may contain prompts, source excerpts or diagnostics. Review them before sharing; redaction is not a comprehensive secret-removal guarantee.</li>
              <li><strong className="text-fg-0">API and PostgreSQL:</strong> optional self-hosted event/queue components after the direct CLI path works. Neither the website, a public API nor a database is needed for the first CLI evaluation.</li>
            </ul>
            <p className="mt-5 text-sm"><a className={LINK} href={`${REPO}/docs/architecture.md`}>Architecture</a> · <a className={LINK} href={`${REPO}/docs/security.md`}>Security boundaries</a> · <a className={LINK} href={`${REPO}/packages/furnace/src/furnace/cli.py`}>CLI source</a></p>
          </section>
          <section id="first" className="scroll-mt-20 pt-8" aria-labelledby="first-h">
            <h2 id="first-h" className="font-display text-3xl font-semibold">Your first evaluation</h2>
            <p className="my-5 text-sm leading-relaxed text-fg-2">Commands below use PowerShell from the repository root. Replace OWNER/REPO, PR and endpoint/model placeholders. Help commands were checked locally; this full onboarding has not been executed with a new developer in a clean environment.</p>
            <Step title="1. Get the code and validate local tools">
              <Command>{`git clone https://github.com/dilipna/Furnace4LLM.git
cd Furnace4LLM
uv sync --frozen
uv run furnace gh-guard --help
uv run furnace gh-repair --help
docker version`}</Command>
              <p>Success: dependencies resolve, CLI help displays the suite/questions options, and Docker reports both client and server. Do not continue to remote writes until these work.</p>
            </Step>
            <Step title="2. Review access, then configure one repository">
              <p>The GitHub App requests repository contents and pull-request write access, checks write access and metadata read access; it requests no organization permissions. Tokens for source reads and check/PR writes are scoped separately. The implementation restricts generated branches to furnace/*; that is an application rule, not a GitHub permission limiting all writes to that prefix.</p>
              <p>Only with the repository owner’s consent, review the manifest and install the App on that repository:</p>
              <Command>{`uv run furnace gh-setup --name furnace-pilot-UNIQUE
uv run furnace gh-check`}</Command>
              <p>Keep the private key outside the checkout. App setup records its ID, key path and webhook secret in private configuration. Do not paste these into issues. For private repositories, choose an approved webhook transport; the default public smee channel is not private transport.</p>
              <p>In the runner’s private .env, set the following configuration (these are file entries, not PowerShell commands). No paid judge is needed:</p>
              <Command>{`FURNACE_GITHUB_ALLOWED_REPOS=OWNER/REPO
FURNACE_GUARD_AUTO_REPAIR=false
FURNACE_LAB_BASE_URL=http://YOUR-MODEL-SERVER:8000/v1
FURNACE_LAB_MODEL=YOUR-SERVED-MODEL-ID`}</Command>
              <p>Success: gh-check returns App information. Confirm its installation includes the intended repository. It does not establish model-server performance or workload fit.</p>
            </Step>
            <Step title="3. Prepare trusted checks and representative questions">
              <p>Create pilot_suite.py on the trusted runner. Review its imports; this is host-executed Python. Replace the test target if your repository uses a different one:</p>
              <Command>{`from furnace.guardian.impact import SuiteItem

SUITE = [
    SuiteItem("unit:tests", "unit", [], set(), always=True),
    SuiteItem("check:prompt_prefix_stable", "check", [], set(), always=True),
    SuiteItem("bench:chat_perf_gate", "benchmark", [], set(), always=True),
]`}</Command>
              <p>Create pilot_questions.json as a JSON list of representative sanitized strings. For example, [&quot;How do I reset my password?&quot;] is valid syntax, not a validated workload for your app. This initial suite selects every listed check; no graph-targeting savings are claimed.</p>
            </Step>
            <Step title="4. Validate the sandbox, then measure the change">
              <Command>{`uv run furnace gh-forge OWNER/REPO --questions pilot_questions.json
uv run furnace gh-guard OWNER/REPO PR --suite pilot_suite.py --questions pilot_questions.json`}</Command>
              <p>Forge without --open-pr is a sandbox-validated dry run. Guard writes a GitHub check and loads your model server: obtain consent before running it. Success is a completed report on the intended base/head with evidence for each executed check. Record revision IDs, suite/question hashes, server/model configuration and timestamps; an interrupted attempt is not a successful evaluation.</p>
              <p>If slicing refuses the handler or test installation fails, use recovery below. Do not import untrusted app code on the host to bypass a refusal.</p>
            </Step>
            <Step title="5. Inspect a supported repair, if one applies">
              <Command>{`uv run furnace gh-repair OWNER/REPO PR --suite pilot_suite.py --questions pilot_questions.json`}</Command>
              <p>Without --open-pr this is a dry run. With no endpoint, --no-endpoint can produce a functional-only proposal: <strong className="text-fg-0">Functionally tested; performance unverified</strong>. Review its behavior changes. Adding --open-pr is separate consent to create a draft; Furnace never merges.</p>
              <p><a className={LINK} href={`${REPO}/docs/pilot/README.md`}>Full supervised runbook, optional event mode and evidence to retain</a></p>
            </Step>
          </section>
        </div>
        <OutcomeGuide />
        <section id="recovery" aria-labelledby="recovery-h" className="mx-auto w-full max-w-[1100px] scroll-mt-20 px-4 py-12 sm:px-6">
          <h2 id="recovery-h" className="font-display text-3xl font-semibold">Recover, stop or remove the integration</h2>
          <dl className="mt-6 space-y-5 text-sm leading-relaxed text-fg-2">
            <div><dt className="font-semibold text-fg-0">uv or Docker fails</dt><dd>Install the prerequisites first; run uv sync --frozen again and confirm Docker’s daemon is running. Inspect the actual error. Dependency installation interrupted? Do not assume its existing cache is complete; inspect the dedicated dependency volume and remove only that pilot-owned volume before retrying. Do not prune Docker globally.</dd></div>
            <div><dt className="font-semibold text-fg-0">Authentication or repository access fails</dt><dd>Run gh-check, verify the App installation includes this repository, key path exists, and the allowlist matches OWNER/REPO. Reauthorize through the owner; never paste the key or secret into logs or website inputs.</dd></div>
            <div><dt className="font-semibold text-fg-0">Endpoint or slicing fails; measurements are inconclusive</dt><dd>Confirm the configured /v1 endpoint is reachable from the runner and the model ID matches the served model. Inspect Docker and slicing diagnostics. For uncertain measurements, review representative inputs and server load before collecting more data. Preserve failed or unfavorable results; do not lower thresholds.</dd></div>
            <div><dt className="font-semibold text-fg-0">Stop and uninstall</dt><dd>Stop pilot-owned CLI, poller and runner processes (Ctrl+C in their terminals). Uninstall or restrict the GitHub App, and revoke its private key if appropriate. Remove pilot .env, key, snapshots and logs under your retention policy. Stop the database only if dedicated to this pilot; inspect names before deleting any pilot-owned volumes. No Docker-wide pruning or shared-volume deletion.</dd></div>
          </dl>
          <p className="mt-6 text-sm text-fg-2">Do not install yet if fit is unclear. Inspect the <a className={LINK} href={`${REPO}/docs/pilot/discovery.md`}>discovery checklist</a>, <a className={LINK} href={`${REPO}/docs/engineering-review.md`}>engineering review</a> and <Link className={LINK} href="/bench">recorded evidence with limits</Link>. A supervised pilot is proposed; no participant results are claimed.</p>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
