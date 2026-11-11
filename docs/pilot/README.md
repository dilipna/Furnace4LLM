# Supervised external-developer pilot

This is a proposed pilot, not a customer result or a production-readiness claim.
Start with one developer, one repository and one supervised evaluation. Use the
[discovery checklist](discovery.md) and leave [outcomes](evidence-template.md) blank
until observed. The new repair-verification branch depends on unmerged PR #5 at
`d1dfad9e5a0e816cf6a38bc588c555fe196813cc`.

## Fit and boundaries

Fits: Python applications with sliceable prompt-building handlers, tests runnable with
requirements files, a team-controlled OpenAI-compatible model endpoint, Docker, and
permission to install a GitHub App on one repository. vLLM is the measured server path;
other adapters are not a demonstrated pilot configuration. The GPU may be on another
machine accessible to the runner; a GPU is not necessary for structural/offline proposals.

Do not promise support for arbitrary Python handlers, hosted-model latency, JavaScript/
TypeScript extraction, fork PR execution, general repair, production multitenancy, or
answer equivalence. Repair supports one prefix-instability family. AST slicing can refuse
a handler. Existing tests plus a prefix test are not a semantic-equivalence guarantee.

The public website is a recorded demonstration plus a browser-local structural checker.
It cannot run a partner's GitHub jobs or model benchmarks. A browser prefix pass says
nothing about cache hits or latency. The local CLI/runner uses real code and the chosen
endpoint; describe each result with its source and timestamps.

## Minimum onboarding (PowerShell, repository root)

Have Python 3.12/uv, Git, Docker Desktop/Linux Docker, and a disposable test repository or
a reviewed same-repository PR. Do not use a production repository for first fault injection.
The first CLI evaluation does not need the UI, a public API or a hosted database.

```powershell
uv sync --frozen
uv run furnace gh-guard --help
uv run furnace gh-repair --help
docker version
```

These dependency/help commands are locally executable. Docker sandbox checks and fixture
repair were tested locally. The credentialed partner steps below are code-traced and
prepared, not executed for an external developer.

1. Review the App manifest and install on **only** the chosen repository:
   `uv run furnace gh-setup --name furnace-pilot-<unique-name>`. This creates a remote App
   and requires the partner's consent. For a private repository, use their own approved
   webhook endpoint; the setup default smee channel is not a private transport.
   `uv run furnace gh-check` validates configuration; do not paste its secrets or key.
2. In the runner's private `.env`, set `FURNACE_GITHUB_ALLOWED_REPOS=OWNER/REPO`,
   `FURNACE_GUARD_AUTO_REPAIR=false`, `FURNACE_LAB_BASE_URL=<approved endpoint>/v1`,
   `FURNACE_LAB_MODEL=<served model id>`. App setup records App ID, key path and webhook
   secret; the private key belongs outside the checkout. No provider key is needed for
   the deterministic/performance path. Do not enable a paid judge for this pilot.
3. Create a **trusted local** `pilot_suite.py` and `pilot_questions.json`. Suite Python is
   executed by `cli._suite` on the runner host; it is not untrusted repository code to run
   outside the sandbox. Review it and its imports. Questions must be a JSON list of
   representative sanitized strings; agree why they represent the real workload.
4. Start conservatively with this suite (replace the test target if needed):

```python
from furnace.guardian.impact import SuiteItem

SUITE = [
    SuiteItem("unit:tests", "unit", [], set(), always=True),
    SuiteItem("check:prompt_prefix_stable", "check", [], set(), always=True),
    SuiteItem("bench:chat_perf_gate", "benchmark", [], set(), always=True),
]
```

This deliberately selects all three checks for the first evaluation. It does not claim
graph-targeting savings. Review node bindings and an unaffected change only after the
baseline is valid. Furnace cannot manufacture the partner's suite or representative inputs.

5. Confirm Docker test installation can run the app's requirements and that prompt slicing
   succeeds. Run `uv run furnace gh-forge OWNER/REPO --questions pilot_questions.json`
   **without** `--open-pr` for a sandbox-validated dry run. A refusal is an outcome to record,
   not a reason to execute arbitrary repository imports on the host or weaken the harness.
6. A supervised measured evaluation writes a GitHub check and calls the model server:
   `uv run furnace gh-guard OWNER/REPO PR --suite pilot_suite.py --questions pilot_questions.json`.
   Obtain partner consent for that write and inference load. Record base/head, suite and
   question hashes, server configuration, GPU/power state and run timestamps. Review PASS,
   BLOCK or INCONCLUSIVE with the developer; do not turn unknowns into passes.
7. If a supported regression is present, first use dry-run repair:
   `uv run furnace gh-repair OWNER/REPO PR --suite pilot_suite.py --questions pilot_questions.json`.
   Measured `verified` requires the existing interval rule and passing sandbox tests.
   No endpoint (`--no-endpoint`) yields `functional_only`, not a latency claim.
   `--open-pr` is separate consent to create a draft; offline drafts prominently say
   performance UNVERIFIED. They do not satisfy automatic measured-repair requirements.

Optional event mode, only after the CLI path works: `docker compose up -d postgres`,
`uv run poe migrate`, configure the trusted absolute suite/questions paths in
`FURNACE_GUARD_SUITE_PATH` / `FURNACE_GUARD_QUESTIONS_PATH`, then run `uv run poe runner`
and `uv run poe gh-poll` in separate terminals. Postgres/queues belong to this trusted
single-team deployment. A public unauthenticated control plane is not a pilot prerequisite.

## Data, credentials and cleanup

Repository snapshots and rendered prompts are processed on the runner; prompts are sent
to the configured model endpoint. Test code runs in disposable Docker copies. Dependency
installation has network access and can execute package install scripts. Excerpts are
redacted, but do not promise comprehensive secret removal. Never include production secrets
in pilot examples. Read-only source tokens and check/PR write tokens are separately scoped.

GitHub receives checks, annotations and draft content; local logs/results may contain
source excerpts, prompts or diagnostics. Decide retention with the partner before running.
Review output before sharing it. Functional-only proposals can alter model-visible values;
a person must review behavior and semantic consequences before any merge.

At exit: stop only pilot-owned processes; uninstall/restrict the App, revoke its private
key if appropriate, and remove the pilot's `.env`, key, snapshots and logs per the agreed
retention policy. Stop the pilot database only if it is dedicated. Inspect named dependency
volumes before removing specific pilot-owned ones; **do not** run Docker-wide pruning or
delete shared volumes. Interrupted dependency installation is still an open reliability
issue; see [the next-step plan](../follow-ups/002-interrupted-dependency-cache-plan.md).

Success is one valid, representative evaluation that helps a real release decision.
Unknown setup effort, time savings and adoption remain unknown until recorded.
