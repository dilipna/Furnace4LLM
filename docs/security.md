# Security

Furnace reads other people's code, runs parts of it, and writes pull requests. The design
treats every repository as untrusted input and every write as something a human approves.
Each control below names the test that checks it; anything without a test says so.

## Threat model

| asset | threat | where it could come from |
|---|---|---|
| host machine (laptop runner) | code execution, file access, network pivot | repository code run by evals, tests, harnesses |
| customer repositories | unwanted writes, merges, secret leaks | GitHub tokens, bugs in Forge/repair |
| internal network / cloud metadata | SSRF | user-supplied endpoint URLs |
| service | resource exhaustion | archive bombs, huge repos, runaway processes |
| secrets in source | disclosure in UI, logs or excerpts | evidence excerpts shown in the Blueprint |

## Controls

| control | implementation | checked by |
|---|---|---|
| Safe archive extraction: no path traversal, absolute paths, symlinks/hardlinks; entry-count, total-bytes and compression-ratio limits; streaming byte cap on downloads | `security/safe_extract.py`, `ingest/sources.py` | `tests/test_security.py` (zip slip, absolute, symlink, bomb ratio, total bytes, entry count, tar traversal, tar links) |
| Secret redaction in evidence excerpts (known token formats, high-entropy assignments, DB URL passwords) | `security/redact.py`, applied by the extractor before storing excerpts | `tests/test_security.py` (formats, entropy, placeholders not flagged, line numbers) |
| SSRF: endpoint URLs resolve once, every address must be public (private, loopback, link-local, metadata 169.254.169.254 blocked); private only with explicit opt-in | `security/ssrf.py` | `tests/test_security.py` (blocked/allowed IPs, URL rejections, explicit private) |
| DNS-rebinding defense: connection pinned to the validated IP, Host/SNI preserved; each redirect hop re-validated | `security/ssrf.py` (`PinnedTransport`, `safe_get`) | `tests/test_security.py::test_dns_rebinding_is_defeated_by_pinning` (pinned IP, single resolution, redirect to metadata IP refused), `test_pinned_transport_refuses_a_different_host` |
| Sandbox for repository code: disposable copy, `--network none` (or the internal lab network only), read-only root FS, all capabilities dropped, no-new-privileges, non-root uid 10001, pids/memory/CPU limits, hard timeout; only the repo copy and a read-only dependency volume mounted | `sandbox/docker_sandbox.py` | `tests/test_sandbox_escape.py`: outbound TCP and DNS blocked, root-FS write blocked, setuid(0) blocked, uid 10001, lab network has no internet, other networks refused, path escapes refused, timeout enforced |
| Residual: dependency install phase (`pip install -r requirements.txt`) runs with network so install scripts execute there, isolated from host secrets and with the same unprivileged limits | `sandbox/docker_sandbox.py` | documented risk, not eliminated |
| GitHub least privilege: one installation token per job, scoped to one repository and the job's permissions (scan: contents read; Guard: contents + pull requests read, checks write; PR creation: contents + pull requests write) | `github/client.py`, `github/flows.py` | `tests/test_github.py` (token scope), `tests/test_github_flows.py` (Guard uses only its scope and writes only the check run) |
| Never merge, never write a default branch; draft PRs only; branch ref created only after the commit exists | `github/client.py::open_draft_pr` | `tests/test_github.py` (Git Data API order, refuses default branch) |
| No duplicate or overwriting writes on retries: the same change set (content-addressed tree) returns the existing draft PR, open or closed; a branch holding other content is never overwritten; the Guard check run is reused per head commit and only this App's runs are considered | `github/client.py::open_draft_pr`, `find_check`; `github/flows.py::guard_pr` | `tests/test_github.py` (retry, closed PR, crash resume, never overwrite), `tests/test_github_flows.py` (reuse, takeover, App-scoped lookup) |
| Explicit write consent: Forge and repair open a PR only with `--open-pr`; event-driven repair only with `FURNACE_GUARD_AUTO_REPAIR=true`; otherwise dry run | `cli.py`, `github/jobs.py` | `tests/test_github_jobs.py` (no repair without consent; one per head commit) |
| Fork pull requests refused by default (their code would run in the sandbox) | `github/flows.py::_pull`, `github/events.py` | `tests/test_github_flows.py`, `apps/api/tests/test_github_webhook.py` |
| Installation isolation: a job created from an event acts only under that event's installation; a repository now under another installation is refused before a token is minted; optional repository allowlist | `github/flows.py::_token`, `github/events.py` | `test_guard_pr_refuses_to_act_under_another_installation`, `test_repositories_outside_the_allowlist_are_ignored` |
| A failing, timed-out or cancelled Guard run completes its check run as neutral (never stuck in progress); a superseded head is skipped | `github/flows.py::guard_pr` | `tests/test_github_flows.py` |
| Webhook authenticity: HMAC-SHA256 over the raw body, constant-time compare; body capped at 5 MB before parsing; payload shape validated (owner/name, 40-hex sha, integer ids) before any write | `apps/api/.../routers/github.py`, `github/events.py` | `tests/test_github.py`, `apps/api/tests/test_github_webhook.py` (bad signature, malformed, oversized) |
| Replay and redelivery: each delivery GUID is processed once (primary key), with an audit row of the decision; at most one active Guard job per PR head commit | `github/events.py`, `db/models.py::WebhookDelivery`, `jobs/queue.py::enqueue_once` | `test_a_replayed_delivery_is_a_no_op`, `test_two_events_for_the_same_head_commit_share_one_job`, `test_concurrent_enqueue_once_creates_exactly_one` |
| Pull-mode webhooks (`gh-poll`): events are read from GitHub's API with the App's own JWT over TLS; authenticity comes from that channel, not HMAC (the API re-serializes payloads); deduplicated with push by GUID | `github/deliveries.py` | `tests/test_github_setup.py` (once per GUID, no old history, malformed reported once) |
| Credentials never leave in errors: GitHub tokens, JWTs and bearer values are scrubbed from every `GitHubError` (they become job errors, job events and neutral check summaries) and are never part of results or progress output | `github/client.py::scrub` | `tests/test_github.py::test_github_errors_never_carry_credentials`, `tests/test_adversarial.py` |
| App permissions as code: `gh-setup` creates the App from a manifest with exactly contents/pull requests/checks write and metadata read, one event; the callback is bound to 127.0.0.1 and checks a random state; the key is written outside the repository, nothing secret is printed | `github/setup.py` | `tests/test_github_setup.py` |
| Job execution: claims fenced by (worker, attempt) so a stalled worker cannot overwrite the outcome of the claim that replaced it; a lost lease cancels the running handler; hard per-job timeout; bounded attempts; configuration errors fail the job, not the runner | `jobs/queue.py`, `jobs/worker.py`, `github/jobs.py` | `tests/test_jobs_queue.py`, `tests/test_github_jobs.py` |
| Production configuration refuses development secrets and writable labels | `settings.py` | `tests/test_security.py::test_production_refuses_dev_secrets` |
| Read-only results API cannot escape its directory (campaign and scenario names validated) | `apps/api/furnace_api/routers/bench.py` | `apps/api/tests/test_bench.py` |
| Source is data, not instructions | reconstruction is deterministic (AST, configs, docs); no LLM reads repository text today | by construction; the planned LLM synthesis step must keep it |

## Not built yet (known gaps)

- User authentication, organizations and Postgres row-level security; the hosted API serves
  public scans and read-only results only. Cross-org access tests come with auth.
- BYOK key storage (encrypted at rest): no provider keys are stored by the service today.
- Container isolation stronger than Docker (gVisor) is a later step.
- With `gh-setup`'s default, the App's webhook URL is a smee.io channel: unguessable but
  unauthenticated, so anyone holding the URL can read event payloads (public data for a
  public demo repository; use `--webhook-url` with your own endpoint for private ones).
- The repair job runs repository code (the sandbox) after Guard; consent is a runner-wide
  setting, not per repository or per pull request.

## Adversarial regression suite

`uv run poe adversarial` runs only the attack-path tests (marker `adversarial`): archive
traversal, links and bombs; secret redaction; SSRF and DNS rebinding; sandbox escapes;
forged, replayed, malformed and oversized webhooks; fork and cross-installation refusal;
never writing a default branch or overwriting a branch; credential scrubbing; App setup
state check; stale job claims and lost leases. The sandbox tests need Docker; the webhook
and queue tests need Postgres.

## Reporting

Report suspected vulnerabilities privately to the maintainer; do not open public issues.
