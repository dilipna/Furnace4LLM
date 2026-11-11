# Visitor journeys and release handoff

## Scope and release base

Local branch: `improve/visitor-journeys`. Parent/base:
`8716c9c72d61b0aa19c012696a6520cba85ed578` (PR #6). Review only the website/documentation
diff above that commit. No retry or repair implementation is duplicated or changed.
Dependency-cache implementation and historical measurement artifacts are untouched.

Read-only GitHub inspection on 2026-11-11: PR #5 is open/mergeable, head
`d1dfad9e5a0e816cf6a38bc588c555fe196813cc`, base main at
`9b88ccc11cafe9b3c5b51ffe4a172698868a7763`; CI 49 and evidence 10 successful.
PR #6 is open/mergeable, head `8716c9c72d61b0aa19c012696a6520cba85ed578`,
base audit/reliability at d1dfad9; CI 50 and evidence 11 successful.
Neither has submitted reviews or inline review threads. These facts are not review approval.
No additional correctness blocker was established by this website-focused review.
The dependency-cache defect is still tracked separately; do not promise interrupted
installation safety.

Merge #5 first, with explicit authorization. Then retarget/integrate #6 against main
and require fresh head checks. Its stacked checks are not main integration evidence.
If the parent was squash/rebase merged, transplant only #6's three child commits;
do not duplicate d1dfad9. Bring only this branch's website/documentation commits onto
the resulting accepted base and rerun web/evidence checks before publication.
The website links to main's repair contract and pilot docs intentionally: those links
must exist on main before publishing this website. Do not release the new status
explanations ahead of the implementation they describe.
No merge, push, deployment, outreach or paid execution was performed for this change.

## Deployed audit observations

Audited https://furnace-5h6.pages.dev using a browser, then traced implementation.
Screenshots are delivered separately in the local handoff's `screenshots/` directory.

| Journey / location | Concrete blocker | Change |
| --- | --- | --- |
| First visitor, home hero | “Ship the prompt. Keep the speed.” plus cache terminology; primary action was the structural checker, no app-fit path in main navigation. | Plain problem/target/scope, recorded demo and fit actions, visible website availability and TTFT definition. Existing measurement inspector retained. |
| Manager, demo first screen | Silent rehearsal before a short explanation; detailed measurements required technical reading. Text said answers stayed the same despite a skipped judge. | Five-step text/visual sequence before video, explicit semantic change and skipped judge, optional exact diffs/statistics. Evidence limits preserved. |
| Developer, /pilot | Installation began with App creation; optional queue/database looked mandatory; no complete first-evaluation/recovery/removal path. GPU appeared required on runner itself. | Prerequisites, component/data map, direct CLI path, trusted suite and questions, success signals, scoped permissions, remote GPU option, recovery and cleanup. No guaranteed pilot outcome or setup time. |
| Results, shared badge/guide | functional_only fell back to a raw idle word; no next actions for interrupted or missing measurements. | Explicit functional-only wording, distinct measured/unknown/failure states, next actions and unchanged exact rules. |
| Recorded navigation loading/error | Claimed a hosted API was sleeping on a static recorded site. | Recorded-specific loading/error copy without an API wake-up promise. |
| Reading / navigation | Small low-contrast secondary dark text; fit link missing from home footer. | Brighter muted text, readable new descriptions, fit/architecture links and keyboard skip targets. Identity and reduced-motion behavior retained. |

## Outcome source of truth

- `packages/furnace/src/furnace/guardian/repair/loop.py`, GitHub flows and `docs/repair-verification.md`:
  functional-only tests do not verify performance. Complete current evidence plus
  unchanged interval/run rules is required for measured verified; human review remains.
- `guardian/perf_gate.py::_verdict`: upper <=10 PASS; lower >10 and point >25 BLOCK;
  smaller certain regressions WARN; crossing tolerance INCONCLUSIVE. Validity/failure
  guards can also block or refuse measurement; inspect reasons, not just a label.
- `github/flows.py` and `jobs/worker.py`: interrupted checks require action and do not become
  reusable successful jobs; queued retries respect their attempt limit and identity.
- `guardian/execute.py`: skipped checks are not measured passes. A GitHub success
  conclusion can aggregate executed checks without proving skipped answer-quality checks.

## Verification and limits

See the accompanying local handoff for exact tested revision, commands, results,
screenshots and browser observations. Historical GPU studies remain historical;
read-only artifact checks and browser interactions are new execution evidence, not
fresh inference. No human usability results, clean-environment developer onboarding,
real iPhone/Safari, live product GitHub run or new GPU inference are claimed.

The [five-task human test and blank results](pilot/visitor-test.md) are ready to use.
Release remains blocked on authorized parent integration, fresh main-based checks,
review of this website diff, and separate push/deploy authorization.
