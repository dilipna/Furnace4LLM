# Studio framework runtime: local verification, 2026-11-13

Executable source: **8af4b42899a286ca1190007c3a92d6df4b9afd01**, branch
`product/researcher-starter`. This record adds documentation only. No push, merge,
deployment, billing activation, cloud resource or new model/GPU inference occurred.

## Result

Studio can run its authored infrastructure fixture in an isolated local Docker worker,
execute bounded requests and exact-output framework checks, persist partial evidence,
stop failed execution and reconcile workers after restart. This is not a learned model,
a model compatibility certification or a complete hosted managed service.

- Relevant Windows regression suite: 96 passed, one symlink-permission skip and one
  existing Starlette/httpx warning, before final app-level lease integration.
- Final targeted API/lease suite: nine passed. The app-level regression rejects a
  concurrent application owner, verifies the first container remains running and
  executes a real request on it. Separate tests cover process-crash lock release.
- Final installed-wheel HTTP smoke passed: project/preferences/case persistence,
  actual prediction/evaluation and exported run identity, duplicate-process refusal,
  real process-tree crash with an orphaned running worker, restart reconciliation,
  rotated token and old-token rejection, timeout/container removal, recovery, stop,
  record deletion and unchanged model source. The first installed run exposed missing
  acquisition of the lease helper; 8af4b42 integrates it and verifies the repeat.
- Source-preview browser observations: real worker readiness, output, exact check,
  timeout/restart and a real six-file ZIP download containing evaluation evidence.
  Confirmed corrected no-output/disabled-request state after failure. At 390px and
  768px there was no horizontal overflow; observed keyboard Tab navigation from
  Evaluations to Activity and into Case name. This is partial UI/accessibility QA,
  not human comprehension evidence. Human results remain blank in the application guide.
- Whole-repository lint, formatting, import boundaries and Pyright passed locally.
  JavaScript syntax passed. Temporary Studio workers and preview processes were removed.
  The repair-verification and visitor-journeys worktrees remained clean.

## Linux check and exact workaround

Unmodified `bash scripts/ci_linux.sh python` on 9f3fffb passed dependency installation,
Ruff, formatting and imports, then failed before tests. Pyright's `nodeenv` bootstrap
raised `ValueError: invalid literal for int() with base 10: '0-alpha'`. It is not a pass.

The final committed source above was checked using the same script with only its Python
runner image replaced by the existing local `furnace-review-toolchain:repair-verification`.
That image adds Node to the uv/Python base:

```dockerfile
FROM node:24-bookworm AS node
FROM ghcr.io/astral-sh/uv:python3.12-bookworm
COPY --from=node /usr/local/bin/node /usr/local/bin/node
```

Observed Node v24.21.0, Python 3.12.12. The runner still archives committed HEAD, uses
uid 1001, real Postgres/migrations, Docker socket access and all non-GPU tests. No test
selection, assertion or acceptance threshold was weakened. **553 passed in 121.19s**,
one existing Starlette/httpx warning; lint, formatting, both import contracts and Pyright
also passed. This was local Linux verification with an explicit bootstrap workaround,
not the unmodified command or hosted CI. Repository workflow/script remain unchanged.
Web and image jobs were not run for this milestone.

## Bundle and limits

Three local wheels plus pinned dependencies and launcher were packaged and installed
outside the checkout. Tested ZIP SHA256:
`dfd6ea8ebdb23f2d83c44a99873d4f6cc99736e0377d2aea326e16287f7b4975`.
The ZIP and raw final Linux log are retained under local `outputs/furnace-studio-runtime/`
in the enclosing task workspace, not published. Hashes detect corruption, not publisher
authenticity. Python/uv remain prerequisites; Docker is optional until fixture execution.

Real research-model adapters, reference inference and task-quality evaluations, GPU
validation, remote compute provisioning, hosted auth/secrets, enforced day-based log
retention, active billing, native signed installation and public downloads remain future
work. Both compute choices are saved preferences; fixture execution is always local.
No historical benchmark measurements or recorded demonstrations were changed or treated
as new execution evidence. See [Studio guide](studio.md) for commands, boundaries,
clean-environment onboarding test and the blank two-person human-review checklist.
