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
| DNS-rebinding defense: connection pinned to the validated IP, Host/SNI preserved | `security/ssrf.py` (`PinnedTransport`) | implemented; **no dedicated test yet** |
| Sandbox for repository code: disposable copy, `--network none` (or the internal lab network only), read-only root FS, all capabilities dropped, no-new-privileges, non-root uid 10001, pids/memory/CPU limits, hard timeout; only the repo copy and a read-only dependency volume mounted | `sandbox/docker_sandbox.py` | `tests/test_sandbox_escape.py`: outbound TCP and DNS blocked, root-FS write blocked, setuid(0) blocked, uid 10001, lab network has no internet, other networks refused, path escapes refused, timeout enforced |
| Residual: dependency install phase (`pip install -r requirements.txt`) runs with network so install scripts execute there, isolated from host secrets and with the same unprivileged limits | `sandbox/docker_sandbox.py` | documented risk, not eliminated |
| GitHub least privilege: one installation token per job, scoped to one repository and the job's permissions (scan: contents read; Guard: contents + pull requests read, checks write; PR creation: contents + pull requests write) | `github/client.py`, `github/flows.py` | `tests/test_github.py` (token scope), `tests/test_github_flows.py` (Guard uses only its scope and writes only the check run) |
| Never merge, never write a default branch; draft PRs only; branch ref created only after the commit exists | `github/client.py::open_draft_pr` | `tests/test_github.py` (Git Data API order, refuses default branch) |
| Explicit write consent: Forge and repair open a PR only with `--open-pr`; otherwise dry run | `cli.py`, `github/flows.py` | code path; covered by the dry-run branch in `flows.py` |
| Fork pull requests refused by default (their code would run in the sandbox) | `github/flows.py::_pull` | `tests/test_github_flows.py` |
| A failing Guard run completes its check run as neutral (never stuck in progress) | `github/flows.py::guard_pr` | `tests/test_github_flows.py` |
| Webhook authenticity: HMAC-SHA256, constant-time compare | `github/client.py::verify_webhook` | `tests/test_github.py` |
| Production configuration refuses development secrets and writable labels | `settings.py` | `tests/test_security.py::test_production_refuses_dev_secrets` |
| Read-only results API cannot escape its directory (campaign and scenario names validated) | `apps/api/furnace_api/routers/bench.py` | `apps/api/tests/test_bench.py` |
| Source is data, not instructions | reconstruction is deterministic (AST, configs, docs); no LLM reads repository text today | by construction; the planned LLM synthesis step must keep it |

## Not built yet (known gaps)

- User authentication, organizations and Postgres row-level security; the hosted API serves
  public scans and read-only results only. Cross-org access tests come with auth.
- BYOK key storage (encrypted at rest): no provider keys are stored by the service today.
- Container isolation stronger than Docker (gVisor) is a later step.
- Webhook-driven runs need a public URL; the runner CLI path does not accept inbound traffic.

## Reporting

Report suspected vulnerabilities privately to the maintainer; do not open public issues.
