# Studio onboarding verification — 2026-11-13

Final executable/UI source: **9f769809bdfc57b5a374e486db5261a6e68e8ea8** on
`product/researcher-starter`. The following verification-record commit changes docs only.
All work is local. No push, deployment, paid service, model download or new GPU inference.

## What changed

- Professional local application layout with clear first actions, a bundled metadata-only
  walkthrough, project preparation, next steps and inspectable execution evidence.
- Read-only environment checks distinguish the available workspace, optional local
  Docker/image readiness and unverified model compatibility. Checks never build images
  or start workers. Missing Docker leaves inspection/editing/export available.
- Example creation is authenticated, respects the two-project limit, preserves edits on
  reopening and works from installed wheels without a model directory or checkout.
- Contract/preference/case drafts stay in browser-tab memory across navigation and status
  refreshes. Request output and Docker consent are project-specific. Unsaved drafts are
  labeled and trigger a close/reload warning. Closing/discarding still loses unsaved data.
- Exact passes, failed assertions, unscored expectations, execution errors and missing
  execution have separate counts. Case labels without matching execution records are
  never counted as passes. Pricing/compute plans remain inactive preferences.
- Friendly missing-uv launcher guidance. A reproducible clean installed-bundle check and
  view-state regressions were added; existing web CI runs the latter without new deps.

## Confirmed correctness defect and reproduction

The real Docker API regression ran three cases: framework_pass, framework_fail, unscored.
After stopping the worker and changing its contract, the evaluation record became null
but the old case labels survived. The new assertion expecting three not_run states failed
before the fix (7.89 seconds). The failure was not hidden, skipped or resolved by changing
an expected model output. Raw evidence summary is in the local task outputs.

`RuntimeService.update` now clears the run and resets case states atomically when contract
or compute preferences change. Case edits already reset their states. The real-worker
regression is parameterized over contract and plan changes and passed afterward; it also
checks actual outputs, distinct request IDs, container removal and source preservation.
The browser additionally suppresses unbound legacy labels when an evaluation record is
missing. Unfavorable assertions remain failures for the unchanged evaluation identity.

## Verification and exact source boundaries

| Evidence | Source and result |
| --- | --- |
| Focused Windows API/starter/runtime/lease tests | 44 passed, 1 symlink-permission skip, 1 existing Starlette/httpx warning on the backend implementation in 60610a5 |
| Local Linux Python + web + image jobs | All passed at 60610a580e04423d415423ce773e300422619a4c. 560 non-GPU Python tests, migrations, lint, format, two import boundaries, Pyright; web builds/tests and API image build/import |
| Final first-action/mobile refinement | 9f76980 changes only three static UI files; Python/runtime code is identical to 60610a5. Module syntax and nine Node state tests passed. Fresh full Linux web job passed at exact 9f76980 |
| Installed Windows worker lifecycle | At 60610a5: real HTTP/output/evaluation/export, duplicate application refusal without stopping first worker, actual process-tree crash, orphan cleanup after restart, token rotation/rejection, timeout removal, recovery, stop and source preservation passed |
| Final installed-bundle clean Linux smoke | Exact final ZIP below: fresh cache, uid 10001, read-only container root, no checkout, no Docker CLI/socket. Missing-uv guidance, installed module MIME/content, guided example/kit bytes, edited contract persistence, normal shutdown/restart, token rotation/rejection and record removal passed |
| Final browser | Guided example opened from first-screen mobile CTA; real source-preview worker request/evaluation produced one exact pass and one unscored result. Status refresh/project switch retained a contract draft; another project showed no prior project's output or consent. After run invalidation, browser showed zero passes/two not_run cases. Real mobile kit download had six files and two not_run cases, no evaluation |
| Responsive/keyboard | 390px/768px checks showed no horizontal overflow. Final mobile layout exposes initial actions earlier and uses 16px form inputs/44px primary targets. Browser controls/focus paths exercised; no full accessibility audit or human comprehension claim |

The full Python runner used the previously documented local preinstalled-Node image
`furnace-review-toolchain:repair-verification` (Node v24.21.0, Python 3.12.12). Only that
runner image differs from the repository's Linux script; dependencies, committed tree,
non-root user, migrations, test selection and assertions are unchanged. The unmodified
runner previously failed during nodeenv bootstrap while parsing '0-alpha'. It was not
rerun or relabeled successful here. The final **web** job used the unmodified repository
script. These are local Linux results; hosted CI was not run or claimed.

## Artifact

`furnace-studio-preview.zip`, source 9f76980.
SHA256: `3e486523089ea04f31259813999c086ae95a1511d99c38ebd238189f61b78516`.
Three workspace wheels, pinned dependencies, launcher, README and wheel hashes. Extract
into a new directory and run `python launch.py`; Python 3.12 and uv are prerequisites.
Optional local Linux Docker is required only for explicit fixture execution. Hashes
verify corruption, not publisher identity. This is not a signed native installer.

Local task outputs: `outputs/furnace-onboarding/` in the enclosing workspace contain the
ZIP, clean Linux report, exact Linux logs, screenshot evidence and earlier installed
smoke report. That installed Windows report identifies 60610a5 and its earlier ZIP hash;
it is separate from the final refined ZIP's clean Linux report. Earlier `clean-linux.json`
is also historical. Use `clean-linux-final.json` for the final artifact.

## Remaining release gates

Fresh Windows/macOS onboarding, a full accessibility review and independent human testing
remain. No participants have taken the human checklist yet. Actual research-model adapters,
reference inference/task-quality evaluations, GPU validation, native signed installation,
public site/download integration, hosted auth/secrets, remote compute, enforced retention,
active billing and production operation remain future work. The guided fixture is a local
infrastructure test, not the complete managed service. No claim of investor/user approval
or product-market fit is supported by automated checks. Historical GPU/demo measurements
were not changed or represented as new execution.

The local preview is retained for review with one metadata-only example and no running
worker. Temporary installed-test processes/workers were removed. The two other worktrees
(repair-verification and visitor-journeys) stayed clean and untouched.

See [Studio guide](studio.md) for setup, scope and the blank two-person human checklist.
