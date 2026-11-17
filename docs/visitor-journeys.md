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

## New execution evidence

Web source tested: `745d3e86e225713bdc72becc547fc15b501dcd1b`.
Local Linux Node 24 container: frozen install, ESLint, Next route type generation,
TypeScript, normal production build, 4 byte-range tests, 17 prefix-check tests,
and recorded static export all passed. The full existing web verifier first passed
at 021a40c; final commits were archived into the same retained verifier container
and its identical web commands rerun successfully. Dependencies were reused on the
final run. No CI workflow or acceptance rule changed. This is local Linux evidence,
not hosted CI on the unpublished website branch. Python/image jobs were not rerun
for this website-only diff.

Windows lint/types and 21 unit tests passed. Windows production build failed first
on restricted Google Fonts access, then on a Turbopack child process exiting before
connection; Linux builds passed. No fallback compiler or font substitution was committed.

New browser checks: desktop 1280/1440, mobile 390x844, tablet 768x1024 in the in-app
browser. Landing → demo → fit, setup anchors, recorded trial switching, optional
statistics, functional-only wording, keyboard focus, silent-video text alternative,
playback and paused keyboard seeking were observed. Paused video time advanced
64.4235 → 66.257498 → 68.0915 seconds by keyboard input. Final mobile heading anchor
is 80px below viewport top (previously 0px under the sticky header); tablet sequence
has two columns. No horizontal page overflow observed; code blocks scroll internally.
Final browser warning/error log was empty. Reduced-motion CSS was inspected;
OS preference toggling, full accessibility conformance and real iPhone/Safari were
not tested. Error-boundary copy was code-reviewed, not fault-injected. Recorded
loading wording is mode-specific; no live-service wake-up promise remains.

The preview was served only from Linux-exported static files, with Furnace API,
runner/model services not started and the existing Furnace Postgres container
stopped during the browser checks. Postgres was restored afterward. Static request
logs contained no /api/ requests. This is request-log plus source inspection, not a
complete browser network capture (resource performance API unavailable in the browser
inspection scope). No product credentials or external App writes were used.
153 static text assets were pattern-scanned with no private-key/GitHub-token/provider-key
pattern hits; this is not a comprehensive secret audit of historical video frames.
Landing/demo/pilot local links and anchors resolved against the export. Links to
new pilot/repair docs on main depend on parent integration before publication.

uv sync --frozen and both documented guard/repair help commands passed locally using
the existing workspace cache; the default sandbox cache was inaccessible. Snapshot
freshness check passed. Saved-study review recomputed 12 runs / 720 historical requests,
confirmed published tables and hashes; structural rehearsal gave expected outcomes
in all 12 conditions. These are new artifact/replay checks, not new GPU inference.
No clean-environment external-developer onboarding or participant test was performed.
