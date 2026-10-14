# Pilot guide: Furnace on one design partner's repository

This is the operational guide behind the `/pilot` page. It says what a pilot needs, how setup
works, and what to do when something is down. Status of the pieces as of 2026-10-14:
everything below runs locally on the fixture apps; the GitHub App path is tested against a
mock GitHub only (no live run is recorded yet, `docs/completion.md` section E); there is no
hosted control plane (`docs/deploy.md` is ready but not deployed).

## Who it fits

| needed | why |
|---|---|
| A Python app that builds prompts in code | Scan and Guard's impact analysis read Python with the standard `ast` module; other languages are reported as not analyzed |
| A model behind an OpenAI-compatible endpoint the team serves | the perf gate replays rendered prompts against it; measured on vLLM only (SGLang and Ollama adapters exist and have never been run) |
| One machine with Docker and an NVIDIA GPU | the runner: sandboxed tests and the benchmark client run there |
| A GitHub repository the team can install an App on | one repository per pilot |

Not supported, and said so up front: latency on hosted APIs (not measured), TypeScript,
repairs for anything other than per-request values at the start of a prompt (other
regressions are refused with a reason), fork pull requests.

## The first session (about two hours)

1. **Fit check (15 min).** Confirm the table above. The partner picks the repository, the
   endpoint, and one recent PR that changed prompts or serving settings.
2. **GitHub App (10 min, the partner).** `uv run furnace gh-setup --name furnace-<org>`
   opens the manifest for review; click Create, install on that one repository only;
   `uv run furnace gh-check` prints the App, its permissions and installations
   (`docs/github-app.md`).
3. **Runner (15 min).** On the GPU machine: Docker running, then
   `docker compose up -d postgres && uv run poe migrate && uv run poe runner`.
4. **Suite and questions (45 min, we write them, the partner reviews).** A suite file
   (`SuiteItem` list, same shape as `fixtures/scenarios/f1_suite.py`) binds each check to the
   graph nodes it covers; a questions file holds real user inputs (no customer data needed:
   paraphrased inputs work) for the perf gate to render prompts with. This is the setup work
   Furnace cannot do on its own yet. Scan's Blueprint is the starting point, and its
   findings are advisory (held-out precision 39/77).
5. **Baseline and one PR (30 min).** `uv run furnace gh-guard <org>/<repo> <PR> --suite <file>
   --questions <file>` posts a check run on that PR's head commit. Without the App, Guard
   runs only on the built-in fixture scenarios (`/guard/<scenario>`); a local command for an
   arbitrary checkout is not built, so the App is required for a partner's repository.
6. **Repair consent (optional).** `FURNACE_GUARD_AUTO_REPAIR=true` lets a supported
   regression produce a draft PR into the PR's branch. Off by default.

The partner leaves with: main's baseline (geometric-mean and p95 TTFT, prefix-cache hit rate,
GPU clock), one PR's Guard verdict with its interval, a draft repair only if one applies, and
a written summary that lists what was inconclusive and what Furnace could not see.

## Configuration (runner settings; `.env` on the runner)

| setting | | meaning |
|---|---|---|
| `FURNACE_GUARD_SUITE_PATH` | required | the suite file |
| `FURNACE_GUARD_QUESTIONS_PATH` | required | inputs the perf gate renders prompts with |
| `FURNACE_GUARD_MAX_PROMPT_TOKENS` | optional | the context budget `check:context_budget` enforces |
| `FURNACE_GITHUB_ALLOWED_REPOS` | recommended | events from other repositories are refused |
| `FURNACE_GUARD_AUTO_REPAIR` | default `false` | consent for draft repair PRs |
| `FURNACE_GITHUB_APP_ID`, `FURNACE_GITHUB_PRIVATE_KEY_PATH`, `FURNACE_GITHUB_WEBHOOK_SECRET` | written by `gh-setup` | the key file lives in `~/.furnace/`, never in the repository |

`furnace.yaml`, which Forge adds to a repository, records what Forge validated. **Guard does
not read it in this release**; the settings above decide. (Until 2026-10-14 its header said
Guard read it and named p95 as the gate metric; both were wrong and are corrected in
`forge/templates.py`.) The gate itself is fixed, not configurable: geometric-mean TTFT per
run, 3 interleaved runs per revision, 90% Welch interval, PASS at or below +10%, BLOCK above
+25% (`docs/gate-revision.md`; validated at these values only).

## Results and what they mean

| result | meaning |
|---|---|
| PASS | measured, whole interval inside the tolerance (or the check passed) |
| FAIL / BLOCK | a check failed / slower than 25% with the whole interval above 10% |
| WARN | whole interval above 10%, change at or below 25% |
| INCONCLUSIVE | measured, interval too wide to decide; not a pass |
| SKIP | deliberately not run, with the reason (e.g. no judge key); never counted as a pass |
| NOT RUN | never attempted because a precondition was missing |
| UNSUPPORTED | outside what repair handles; refused instead of guessed |

## When something is down

| symptom | cause | fix |
|---|---|---|
| `/pilot` shows Control API DOWN | API not running, or a free hosted instance asleep | local: `uv run poe api`; hosted: wait about a minute, then check the service logs |
| Guard runner DOWN, "last seen …" | the runner process stopped or the machine slept | start Docker, then `uv run poe runner`; queued jobs wait and are claimed on start |
| A job stays queued | no runner on the `runner` queue | as above; `GET /api/runners` lists runners and their queues |
| A Guard run ends neutral with an error | timeout, endpoint down, or a cancelled job | the check run says why; a dead endpoint is an ERROR, never a PASS |
| Perf gate INCONCLUSIVE | the interval straddles the tolerance | rerun on a quiet machine; do not loosen the gate (its validation holds only at 10% / 25%) |
| GPU benchmarks refuse to start | laptop on battery | plug in; results on battery are not comparable |
| On Windows, API changes do not show | an orphaned `multiprocessing` child still holds :8010 | stop the stray `spawn_main` python processes, then start the API again |

## Deployment for a pilot

The simplest arrangement that supports the real workflow:

```
partner's GitHub ──webhook──► API (FastAPI; verifies HMAC, enqueues only) ──► Postgres (jobs, results)
                                                                                   ▲
partner's GPU machine: runner (claims jobs; sandbox; benchmark client) ────────────┘
                       └─► partner's vLLM endpoint
browser ──► web (Next.js) ──/api/*──► API
```

- The API never runs repository code; it verifies, records and enqueues. Scans of public
  repositories are static analysis.
- The runner is customer-hosted: code, prompts, keys and the model stay on the partner's
  machine. It needs outbound access to GitHub and to the database.
- Until a hosted control plane exists, the whole stack runs on the runner machine
  (`uv run poe demo-up`), with webhooks read through `uv run poe gh-poll` (no public URL).
- Hosting the API and web: `docs/deploy.md` (Render + Vercel + Supabase, free tiers). Not
  deployed; the owner deferred it on 2026-10-13 (D3).

Not built, and needed before more than a handful of pilots: accounts and organizations
(today one deployment serves one team), per-tenant row isolation in the database, and a
runner token per partner instead of a shared database URL.
