# Integration and interface release map

## Repair review and merge — 2026-11-14

PR #6 was reviewed at 59ea54dcf3df7ea9deab2bb11ae66b8e3fa9f777 against main
9efc38d43e4dcb24472ceb10bb828931ec3682db. No reviews, inline comments or unresolved
threads were present. Main had no enforced required checks/rulesets; all four configured
checks passed on that exact head (CI 43147872862, evidence 43147872885). Its tree matched
reviewed 8716c9c. Fresh local focused repair/GitHub/gate tests passed 84 tests on #6's
exact head. Their sandbox, inference and product GitHub boundaries are mocked.

Review confirmed functional_only is separate from verified in the contract, CLI, JSON
and draft wording. Evidence requires finite intervals, matching metric/method/confidence,
sufficient positive run summaries and counts. Blocking candidate verdicts cannot be
overridden by favorable intervals. The loop and pre-write boundary validate acceptance;
rejection cannot request a write token. Stored jobs preserve verification fields;
website selectors count only verified, and the generic badge treats functional_only
neutrally. The separate website branch adds clearer explanations.

Thresholds and historical evidence are unchanged: 90% interval, at least three runs,
upper bound vs head <0%, upper bound vs base <25%. An undecided required repair bound
cannot verify a repair. INCONCLUSIVE against the separate +10% tolerance may still meet
both repair bounds; rounded labels are not reclassified. Historical accepted repairs
are checked read-only. No correctness blocker was found. #6 merged normally as
d4c92cfb453a79582896404849654ae7c18ee1a7, preserving ancestry.

## PR #7 integration

Main merged into product/researcher-starter without conflict or history rewrite.
The merge changed no files relative to 1603ac2. PR #7 now targets main and stays a draft;
its diff excludes the parent repair patch. Participant/release handoffs are updated.
The exact final head/base and fresh hosted results are recorded in PR #7's integration
section, superseding pre-publication pending entries in REVIEW.md. Earlier bundle and
clean-install receipts remain tied to executable source 3474899, not new installation.

## Two interfaces

| Surface | Intended changes | Current availability |
| --- | --- | --- |
| Public website, apps/web | improve/visitor-journeys at 07ccfff90f025b9452a603be0a517c20deeefcef improves landing/demo/fit paths, outcome wording, contrast, mobile anchors and recorded loading/error text. | Committed local branch; not pushed or deployed here. Its historical handoff predates the now-completed parent merges. |
| Local Studio, apps/api/furnace_api/studio* | PR #7 adds project inspection, kit export, Docker fixture, state/identity fencing, provenance and the real-model limitation guide. | Local preview under review. These improvements are not on the public website. Studio is not a static Pages app. |
| Shared foundations | #6 repair statuses/acceptance and existing historical studies. | On main; no new inference in this integration. |

The website-only diff above #6 changes 15 files; #7's original child diff changes 39.
Changed-file sets do not intersect. A read-only git merge-tree check between the
integrated Studio tree and visitor-journeys found no conflicts. That predicts source
compatibility, not a tested combined release. Website work remains clean at its reported
head, without any rewrite.

There is a messaging overlap to review: visitor-journeys introduces the Python-app
pre-merge workflow, while Studio introduces the researcher infrastructure direction.
Before website publication, distinguish the historical recorded Guard study from the
local Studio preview, current from planned capabilities, and their different prerequisites.
Do not advertise a working native installer, real-model Studio adapter, paid provisioning
or download asset that does not exist. The visitor journey and these distinctions belong
on the PUBLIC site; merging Studio alone will not deliver them. Website message updates
remain a separate review, not additional website development in PR #7.

## Smallest release sequence

1. Review draft #7 and assess participant/installation gates; authorize its merge separately.
2. With separate authorization, integrate the preserved website commits onto accepted
   main without duplication; review the product-message distinction and any download link.
   Obtain fresh combined web/Studio/API/evidence checks. No rewrite is needed now.
3. Build the site with NEXT_PUBLIC_RECORDED_ONLY=true and pnpm build:static. Verify static
   links/outcomes and no live API dependency. Keep the public checker labeled structural
   and the hosted demo recorded; neither launches Studio/model workers. Review any
   downloadable artifact separately, including its exact hash.
4. Obtain explicit publication/deployment approval before publishing the static export
   or an asset. No new backend or model service is required for this release sequence.

## Remaining gates

Fresh local automated browser/API review on the integrated unchanged executable tree
started the real Docker fixture and produced one exact pass plus one unscored case.
The six-file export bound the run to the same project/configuration and labeled it
newly_executed_deterministic_fixture with model_inference=false. After Stop and a
server-side contract edit while /guide was open, browser Back and reload showed zero
passes/two not-run cases. Guide wording separated the unimplemented Studio model adapter
from existing endpoint CLI adapters. Tab from Evaluations reached Activity with visible
focus. No new primary-journey defect was established. These observations do not prove
BFCache was used, broad accessibility conformance, or human understanding.

Use HUMAN_TEST.md's separate participant tasks. Nontechnical comprehension does not
require installing Docker; facilitator operation/explanation is assisted observation.
Feedback is blank. Native clean Windows/macOS installation and broader real-browser
BFCache/accessibility coverage remain unverified. Studio has no real-model adapter.
Historical GPU studies and automated fixture tests establish neither human understanding
nor a model-quality/performance improvement. Cache recovery, installers, billing,
hosted infrastructure, new adapters and GPU experiments remain outside this operation.
