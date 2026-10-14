import type { Metadata } from "next";
import Link from "next/link";
import { VERDICT_MEANING, Verdict } from "@/components/guard/verdict";
import { EvidenceInput } from "@/components/marketing/evidence-input";
import { RunnerStatus } from "@/components/pilot/runner-status";
import { AppHeader } from "@/components/ui/app-header";
import { SiteFooter } from "@/components/ui/site-footer";

export const metadata: Metadata = {
  title: "Pilot setup · Furnace",
  description: "What a Furnace design-partner pilot needs, what it delivers in the first session, and how setup works.",
};

const REPO = "https://github.com/dilipna/Furnace4LLM/blob/main";
const CONTACT = process.env.NEXT_PUBLIC_CONTACT_URL || "https://www.linkedin.com/in/dilip-n-ab1091417/";

const FIT: [boolean, string, string][] = [
  [true, "A Python application that builds its prompts in code", "Scan reads Python with the standard ast module. Other languages are not analyzed."],
  [true, "A model you serve behind an OpenAI-compatible endpoint", "Measured on vLLM. SGLang and Ollama adapters exist but have never been run."],
  [true, "One machine with Docker and an NVIDIA GPU for the runner", "Dependencies install in one container step; your tests then run with no network, as a non-root user, with a time limit."],
  [true, "A GitHub repository you can install an App on", "One repository per pilot; you choose which."],
  [false, "Latency on a hosted API (OpenAI, Anthropic, Groq)", "Not measured yet. Prompt-prefix stability matters there too, but Furnace has no evidence for it."],
];

const FIRST_SESSION = [
  ["Baseline", "main's rendered prompts measured on your endpoint: geometric-mean and p95 time to first token, prefix-cache hit rate, with the GPU clock recorded."],
  ["A real pull request, checked", "One recent PR replayed through Guard: which checks it could affect, which ran, and the gate's verdict with its interval."],
  ["A repair, only if one applies", "If a PR puts per-request values at the start of a prompt, a draft fix that passed the tests and the gate. Otherwise you get a clear statement that nothing supported was found."],
  ["A written summary", "What was measured, what was inconclusive, and what Furnace could not see in your app."],
];

const STEPS: { title: string; who: string; body: string; cmd?: string }[] = [
  {
    title: "Fit check (15 minutes)",
    who: "together",
    body: "We confirm the items above, and you pick the repository, the endpoint and one recent pull request that changed prompts or serving settings.",
  },
  {
    title: "Install the GitHub App on one repository",
    who: "you",
    body: "Created from a manifest that you review before clicking Create. Permissions: read code, write only to new furnace/* branches, open draft PRs, report check runs. No organization permissions.",
    cmd: "uv run furnace gh-setup --name furnace-<your-org>\nuv run furnace gh-check",
  },
  {
    title: "Start the runner on your GPU machine",
    who: "you, with us on a call",
    body: "The runner pulls jobs from the queue. Your code and keys stay on that machine.",
    cmd: "docker compose up -d postgres\nuv run poe migrate\nuv run poe runner",
  },
  {
    title: "Describe your app to Guard",
    who: "we write it, you review it",
    body: "A suite file that ties your checks to the parts of the app they cover, plus a questions file with real user inputs for the benchmark. This is the setup work Furnace cannot yet do on its own.",
    cmd: "FURNACE_GUARD_SUITE_PATH=path/to/suite.py\nFURNACE_GUARD_QUESTIONS_PATH=path/to/questions.json\nFURNACE_GITHUB_ALLOWED_REPOS=your-org/your-repo",
  },
  {
    title: "Run Guard on a pull request",
    who: "Furnace",
    body: "On each push to a pull request, Guard posts a check run on its head commit: PASS, FAIL or INCONCLUSIVE, with the interval and the evidence. Shown once on a public repository (2026-10-14); see the Demo page.",
    cmd: "uv run poe gh-poll        # or a webhook to a hosted API\nuv run furnace gh-guard your-org/your-repo <PR> --suite $FURNACE_GUARD_SUITE_PATH",
  },
  {
    title: "Allow draft repairs (optional)",
    who: "you decide",
    body: "Off by default. When on, a supported regression gets a draft PR into the pull request's branch. It is never merged and never pushed to main.",
    cmd: "FURNACE_GUARD_AUTO_REPAIR=true",
  },
];

const CONFIG: [string, string, string][] = [
  ["FURNACE_GUARD_SUITE_PATH", "required", "Python file listing your checks and the graph nodes each one covers"],
  ["FURNACE_GUARD_QUESTIONS_PATH", "required", "Real inputs used to render prompts for the perf gate"],
  ["FURNACE_GUARD_MAX_PROMPT_TOKENS", "optional", "Context budget the context check enforces"],
  ["FURNACE_GITHUB_ALLOWED_REPOS", "recommended", "Repositories the runner will act on; events from anything else are refused"],
  ["FURNACE_GUARD_AUTO_REPAIR", "default false", "Your consent for draft repair PRs"],
  ["FURNACE_GITHUB_APP_ID, …_PRIVATE_KEY_PATH, …_WEBHOOK_SECRET", "written by gh-setup", "Kept in .env and ~/.furnace on the runner; never printed or uploaded"],
];

const DATA = [
  ["Your code", "Downloaded by the runner with a token scoped to that one repository, and copied into a disposable container. Dependencies install with network access (their install scripts run there, away from your secrets); your code then runs with no network, read-only, with all capabilities dropped."],
  ["Your prompts and answers", "Sent only to your own endpoint. The database keeps results, logs, diffs and the short code excerpts cited as evidence, not a copy of the repository."],
  ["Secrets", "Model keys and the App's private key stay on the runner machine. Error messages are scrubbed of credentials."],
  ["Webhooks", "Accepted only with a valid HMAC signature. Each delivery is processed once, payloads are capped at 5 MB, and pull requests from forks are refused."],
];

function Code({ children }: { children: string }) {
  return (
    <pre className="num mt-3 rounded-[3px] border border-line bg-bg-0 px-3 py-2.5 text-[12px] leading-relaxed break-all whitespace-pre-wrap text-fg-1">
      {children}
    </pre>
  );
}

export default function PilotPage() {
  return (
    <div className="flex min-h-full flex-col">
      <AppHeader active="/pilot" />
      <main className="flex-1">
        <section className="border-b border-line">
          <div className="mx-auto grid w-full max-w-[1200px] gap-10 px-4 pt-14 pb-14 sm:px-6 lg:grid-cols-12">
            <div className="lg:col-span-7">
              <p className="num text-[11.5px] tracking-[0.08em] text-ember uppercase">Design-partner pilot</p>
              <h1 className="mt-4 font-display text-[36px] leading-[1.08] font-semibold tracking-[-0.02em] sm:text-[44px]">
                Furnace on one of your repositories, set up with you.
              </h1>
              <p className="mt-5 max-w-[620px] text-[15px] leading-relaxed text-fg-1">
                The pilot is free. It takes one working session of about two hours, plus a follow-up a week later to see
                what Guard caught on your real pull requests. Setup is hands-on: Furnace does not yet configure an
                arbitrary app by itself, and this page lists exactly what it needs.
              </p>
              <div className="mt-7 flex flex-wrap gap-3">
                <a
                  href={CONTACT}
                  className="inline-flex h-10 items-center rounded-[3px] bg-ember px-5 text-[14px] font-medium text-bg-0 transition-colors duration-150 hover:bg-ember-hi"
                >
                  Ask about a pilot
                </a>
                <Link
                  href="/guard/r1_dynamic_head"
                  className="inline-flex h-10 items-center rounded-[3px] border border-line-strong px-5 text-[14px] text-fg-0 transition-colors duration-150 hover:bg-bg-2"
                >
                  See a recorded run first
                </Link>
              </div>
            </div>
            <div className="lg:col-span-5">
              <RunnerStatus />
              <p className="mt-3 text-[12px] leading-relaxed text-fg-3">
                This deployment’s own runner. During a pilot, the runner is a machine of yours, and this panel shows yours.
              </p>
            </div>
          </div>
        </section>

        <section aria-labelledby="fit-h" className="mx-auto w-full max-w-[1200px] px-4 py-14 sm:px-6">
          <h2 id="fit-h" className="font-display text-[24px] font-semibold tracking-[-0.01em]">Is it a fit?</h2>
          <ul className="mt-6 divide-y divide-line border-y border-line">
            {FIT.map(([ok, t, d]) => (
              <li key={t} className="grid gap-1 py-4 sm:grid-cols-[28px_1fr_1.2fr] sm:gap-4">
                <span aria-hidden="true" className={ok ? "text-ok" : "text-fg-3"}>
                  {ok ? "✓" : "○"}
                </span>
                <span className={`text-[14px] ${ok ? "text-fg-0" : "text-fg-2"}`}>
                  <span className="sr-only">{ok ? "Needed: " : "Not supported: "}</span>
                  {t}
                </span>
                <span className="text-[13px] text-fg-2">{d}</span>
              </li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="scan-h" className="border-t border-line">
          <div className="mx-auto grid w-full max-w-[1200px] gap-8 px-4 py-14 sm:px-6 lg:grid-cols-12">
            <div className="lg:col-span-5">
              <h2 id="scan-h" className="font-display text-[24px] font-semibold tracking-[-0.01em]">
                Before the call: see what Furnace reads
              </h2>
              <p className="mt-3 text-[13px] leading-relaxed text-fg-2">
                Scan a public repository, or upload a zip, to get the map Furnace starts from: LLM call sites, prompts,
                models, serving settings and routes, each tied to a file and line. Nothing is executed during a scan.
              </p>
              <p className="mt-3 text-[13px] leading-relaxed text-fg-2">
                Treat the findings as a starting point. On five apps the scanner had never seen, 39 of its 77 findings were
                right. In the pilot, we check the findings together before Guard relies on any of them.
              </p>
            </div>
            <div className="lg:col-span-7 lg:pt-2">
              <EvidenceInput />
            </div>
          </div>
        </section>

        <section aria-labelledby="get-h" className="border-y border-line bg-bg-1">
          <div className="mx-auto w-full max-w-[1200px] px-4 py-14 sm:px-6">
            <h2 id="get-h" className="font-display text-[24px] font-semibold tracking-[-0.01em]">What you leave the first session with</h2>
            <div className="mt-8 grid gap-px border border-line bg-line sm:grid-cols-2 lg:grid-cols-4">
              {FIRST_SESSION.map(([t, d]) => (
                <div key={t} className="bg-bg-1 p-5">
                  <h3 className="text-[14px] font-medium text-fg-0">{t}</h3>
                  <p className="mt-2 text-[13px] leading-relaxed text-fg-2">{d}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section aria-labelledby="steps-h" className="mx-auto w-full max-w-[1200px] px-4 py-14 sm:px-6">
          <h2 id="steps-h" className="font-display text-[24px] font-semibold tracking-[-0.01em]">Setup, step by step</h2>
          <p className="mt-2 max-w-[700px] text-[13px] text-fg-2">
            The commands are the real ones. Full detail is in the{" "}
            <a className="underline decoration-line-strong underline-offset-2 hover:text-fg-0" href={`${REPO}/docs/pilot.md`}>
              pilot guide
            </a>{" "}
            and the{" "}
            <a className="underline decoration-line-strong underline-offset-2 hover:text-fg-0" href={`${REPO}/docs/github-app.md`}>
              GitHub App guide
            </a>
            .
          </p>
          <ol className="mt-8 space-y-0">
            {STEPS.map((s, i) => (
              <li key={s.title} className="grid gap-3 border-t border-line py-6 md:grid-cols-[48px_1fr_1.1fr] md:gap-6">
                <span className="num text-[13px] text-ember">{String(i + 1).padStart(2, "0")}</span>
                <div>
                  <h3 className="text-[15px] font-medium text-fg-0">{s.title}</h3>
                  <p className="num mt-1 text-[11.5px] text-fg-3">{s.who}</p>
                  <p className="mt-2 text-[13px] leading-relaxed text-fg-2">{s.body}</p>
                </div>
                <div className="min-w-0">{s.cmd && <Code>{s.cmd}</Code>}</div>
              </li>
            ))}
          </ol>
        </section>

        <section aria-labelledby="cfg-h" className="border-t border-line bg-bg-1">
          <div className="mx-auto w-full max-w-[1200px] px-4 py-14 sm:px-6">
            <h2 id="cfg-h" className="font-display text-[24px] font-semibold tracking-[-0.01em]">Configuration</h2>
            <p className="mt-2 max-w-[720px] text-[13px] text-fg-2">
              Guard is configured on the runner machine, in its .env file. These settings are the whole
              configuration; nothing is read from your repository except the code under test. The perf gate itself is
              fixed: geometric-mean TTFT, 3 interleaved runs per revision, a 90% interval, PASS at or below +10%, BLOCK
              above +25%.
            </p>
            <div className="mt-6 overflow-x-auto">
              <table className="w-full min-w-[640px] border-collapse text-left text-[13px]">
                <tbody>
                  {CONFIG.map(([k, req, d]) => (
                    <tr key={k} className="border-b border-line align-top">
                      <td className="num py-3 pr-6 text-[12px] text-fg-0">{k}</td>
                      <td className="py-3 pr-6 text-[12px] whitespace-nowrap text-fg-3">{req}</td>
                      <td className="py-3 text-fg-2">{d}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <section aria-labelledby="verdict-h" className="mx-auto grid w-full max-w-[1200px] gap-12 px-4 py-14 sm:px-6 lg:grid-cols-2">
          <div>
            <h2 id="verdict-h" className="font-display text-[24px] font-semibold tracking-[-0.01em]">What each result means</h2>
            <p className="mt-2 text-[13px] text-fg-2">Every check reports one of these. A skipped check is never counted as passed.</p>
            <dl className="mt-6 space-y-3">
              {VERDICT_MEANING.map(([v, d]) => (
                <div key={v} className="grid grid-cols-[120px_1fr] items-baseline gap-4">
                  <dt>
                    <Verdict v={v} />
                  </dt>
                  <dd className="text-[13px] text-fg-1">{d}</dd>
                </div>
              ))}
            </dl>
          </div>
          <div>
            <h2 className="font-display text-[24px] font-semibold tracking-[-0.01em]">Where your data goes</h2>
            <dl className="mt-6 space-y-4">
              {DATA.map(([t, d]) => (
                <div key={t}>
                  <dt className="text-[13px] font-medium text-fg-0">{t}</dt>
                  <dd className="mt-1 text-[13px] leading-relaxed text-fg-2">{d}</dd>
                </div>
              ))}
            </dl>
            <a className="mt-5 inline-block text-[13px] text-fg-2 underline decoration-line-strong underline-offset-2 hover:text-fg-0" href={`${REPO}/docs/security.md`}>
              Security controls and their tests →
            </a>
          </div>
        </section>

        <section aria-labelledby="terms-h" className="border-t border-line bg-bg-1">
          <div className="mx-auto w-full max-w-[1200px] px-4 py-14 sm:px-6">
            <h2 id="terms-h" className="font-display text-[24px] font-semibold tracking-[-0.01em]">Pilot terms</h2>
            <ul className="mt-6 grid gap-6 text-[13px] text-fg-1 md:grid-cols-3">
              <li>
                <span className="font-medium text-fg-0">Free.</span> There is no billing, and nothing to cancel.
              </li>
              <li>
                <span className="font-medium text-fg-0">What we ask:</span> a 30-minute follow-up and permission to describe
                the result without naming you, unless you agree to be named.
              </li>
              <li>
                <span className="font-medium text-fg-0">Pricing later:</span> not set. The pilots exist partly to learn
                whether teams would pay, and for what.
              </li>
            </ul>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
