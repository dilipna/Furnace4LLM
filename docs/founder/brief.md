# Furnace: founder brief (2026-10-14)

One page for a first conversation with a prospective design partner, advisor or investor.
Every number links to a result file; "hypothesis" marks what has not been tested with
customers. There are no customers, users, revenue, funding or investor conversations yet.

## The product in one sentence

Furnace benchmarks each pull request of a Python LLM application on the team's own model
server, blocks changes that break prompt caching or raise time to first token, and drafts a
fix it has already tested, for a person to review.

## The customer (hypothesis, not yet validated)

**First customer:** a small product team (roughly 2 to 20 engineers) shipping a Python LLM
app on models it serves itself with vLLM or a similar engine, for cost, data residency or a
fine-tuned model. Latency and GPU spend are numbers someone on the team watches.

**Why they would care:** model servers reuse work across requests that start with the same
text. A pull request that puts a request id, a timestamp or a user name at the top of the
prompt removes that reuse. The answers do not change, so answer-quality checks pass, and unless
someone benchmarks the server before merge, the regression shows up in production as
latency and GPU cost. On the fixture app, one such
line took the prefix-cache hit rate from 98% to 0% and raised geometric-mean time to first
token by about 600% (`bench/results/2026-10-12-gate-validation/rq5.md`).

**The event that makes them try it:** a latency or GPU-cost spike traced back to a prompt or
serving change; moving from a hosted API to self-hosting; or a latency commitment to their
own customer. (Hypothesis: we do not yet know how often this happens.)

**What they do today:** eval platforms (promptfoo, Braintrust, LangSmith) score answers on
each PR and also record latency (promptfoo can fail a test above a per-call latency
threshold; LangSmith reports first-token percentiles). Code-benchmark CI (CodSpeed) times
Python functions. Monitoring shows latency and cache hit rates after deploy. What we have not
seen packaged is the specific workflow: render both revisions' prompts with the app's own
code, run them interleaved on the team's own server, decide with an interval rather than a
fixed threshold, read the server's prefix-cache hit rate, point to the line, and draft a fix
checked by the same gate. Teams can assemble parts of this themselves; Furnace packages it
for one case (Python, self-hosted, one regression family).

**First session:** in about two hours on one repository, the team gets main's baseline on
their endpoint, one recent PR checked by the gate with its interval, a draft fix if a
supported regression is present (or a clear "nothing supported found"), and a written list
of what Furnace could not see.

**Why they would keep using it or pay (hypothesis):** it replaces a manual pre-merge
benchmark that teams skip, and one caught regression is worth GPU-hours and user-facing
latency. Payment is untested; candidate models are below.

## What is proven technically (with files)

| claim | evidence |
|---|---|
| The perf gate does not cry wolf on unchanged code | 0/36 false alarms (exact 95% CI 0 to 9.7%), PASS 29/36, rest INCONCLUSIVE; design frozen before validation (`docs/gate-revision.md`, `2026-10-12-gate-validation/validation/report.md`) |
| It blocks the prompt-cache regression | 6/6 BLOCK, median +613% geometric-mean TTFT |
| Repair works for one supported scenario | 3/3 repeated trials of one scenario (fixture F1, regression R1): the regression test fails on the PR and passes on main; the repair is -85.5 to -86.0% vs the PR and +0.9 to +4.2% vs main (90% upper bounds at most +9.5%); it sends byte-identical prompts to main for 34/34 questions; the first strategy was rejected by the same gate (`rq5.md`, `rq5/prompt_identity.md`) |
| Targeted checks | ran 46% of checks with the same conclusion as the full suite on 13/13 scripted PRs, under the gate of 2026-10-06 (later found biased) (`2026-10-06/rq3.md`) |
| Prefix caching matters on a real workload | caching off raised p95 TTFT by +193% to +433% at max-num-seqs 32 (`2026-10-06/rq4/rq4.md`) |
| Engineering | FastAPI + Postgres job queue (leases, fencing, timeouts), Docker sandbox with no network, GitHub App with check runs and idempotent draft PRs, webhook HMAC and dedupe; 393 tests pass in Linux CI containers (`scripts/ci_linux.sh`, 2026-10-14) |

## What is not proven

- **One live GitHub run.** On 2026-10-14 the whole flow ran on a public repository
  (check run on the right commit, draft fix, real webhooks; verification 10/10). The first
  attempt failed at a GitHub permission and was fixed. One run is not a track record.
- **One fixture, one regression family, one GPU, one small model** (Qwen2.5-0.5B on a laptop
  RTX 3050 Ti at 780 MHz). Nothing has been measured on a production-scale model or server.
- **Small regressions:** changes sized at +13% to +30% measured +4% to +7% inside the gate
  and came out INCONCLUSIVE 15/18. The gate catches large regressions; catching ones just
  above its 10% tolerance is not shown. It decides on a geometric mean, so it is not a
  tail-latency (p95) gate.
- **Onboarding is manual:** a suite file per app is written by hand. The scanner that would
  automate it found 32/48 call sites and 39/77 correct findings on five unseen apps (judged
  by the developer, not independently reviewed).
- **Hosted APIs:** prompt-prefix stability also affects OpenAI and Anthropic prompt caching,
  but Furnace has measured nothing there.
- **The optimizer** recommended keeping the baseline config; its independent rerun was
  inconclusive, so no improvement is claimed.

## Business model (hypotheses to test in pilots)

1. Per-repository subscription for the hosted control plane, with a customer-hosted runner.
2. Setup plus support for teams that want the suite written for them (closer to services
   early on).
3. Usage-based on gate runs (weak: the GPU time is the customer's).

None has been priced with a customer. The pilot is free.

## Known operating costs

- Today: one laptop GPU, and free tiers for the planned hosted control plane (Render, Vercel,
  Supabase; not deployed). The model and GPU in a pilot are the partner's.
- Per pull request, on the laptop: a live Guard run took 84 to 86 s with the endpoint up
  (2026-10-09, `CONTINUE.md`); a repair attempt took 196 to 203 s (`rq5.md`). The cost is
  GPU minutes on the partner's machine.
- Unknown: support time per pilot (the suite file is the main cost to learn).

## Next milestones

1. The live GitHub run on a public demo repository: webhook, check run on the right commit,
   draft repair PR, recorded (blocked on creating the App and the repository).
2. Three design-partner pilots on real repositories (`docs/founder/validation-plan.md`).
3. Write the suite file automatically from the Blueprint for apps like the pilots'.
4. A hosted control plane for the pilots' results, with per-team isolation.

## The ask

Introductions to teams that serve their own models in production, and 30-minute
conversations about how they catch latency regressions today. Not raising money.

## What must be true before a fundraising conversation is credible

- At least a few teams describe this problem unprompted and have hit it recently.
- Pilots on real repositories where Furnace caught something the team cared about, or a
  clear finding that it did not.
- Evidence that onboarding gets from hours of hand setup to something a team can do alone.
- A first price that someone has agreed to pay, even in a letter of intent.
