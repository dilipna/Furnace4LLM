# Portfolio convergence — 2026-11-21

## Integration

PR #13 was reviewed at unchanged `b4fe39f`. No submitted reviews or unresolved threads;
the expected hosted workflows passed. Focused pre-merge lifecycle/evidence tests passed
28 tests. It merged normally as `c34ddeeb1b7b058737402e24e3e86ad8c76720ae`.
[Main CI](https://github.com/dilipna/Furnace4LLM/actions/runs/44977810731) and
[main evidence](https://github.com/dilipna/Furnace4LLM/actions/runs/44977810730) passed.

PR #14 includes main via merge commit `9056f93225af97fcca2d553842c1e9ed314dd280` and
now targets main. No shared history was rewritten. Its source, preflight, adapter,
cleanup and packaging paths were reviewed. A packaging blocker was reproduced:
`--skip-build` labelled a ZIP recording source `481b960` as release source `d0caf157`.
It now refuses mismatched source/version/dirty state, wheel inventory and changed bytes
before replacing output. Seven regressions passed; an actual stale bundle was refused,
and a fresh clean candidate was packaged successfully. Historical platform records
now include their source commit and are explicitly not tests of the new ZIP.

[PR #14 CI](https://github.com/dilipna/Furnace4LLM/actions/runs/44978375483) passed on
`9056f93`: **712 passed, 1 skipped** in Python, plus Web/Studio and API image.
[Evidence](https://github.com/dilipna/Furnace4LLM/actions/runs/44978375473) also passed.
PR #14 remains unmerged pending Dilip's approval. No artifact was published or deployed.

## Housekeeping and curation

GitHub closed #11 when its work was integrated through #13; it is labelled
`superseded-by-13`. Its branch was retained. #1 remains open and labelled `earlier-work`:
patch comparison found branch-specific evidence-gate commits and a distinct incomplete
benchmark regression. Those need semantic accounting before proposing closure, not a
blind merge of the older implementation. No branches were deleted.

The original `design/product-experience` branch remains at `9b7e74c`, with its evidence.
Only its readable evidence-export change was selected onto #14 as `b5c16a9`, in
[draft PR #15](https://github.com/dilipna/Furnace4LLM/pull/15): six files, no broader UI
redesign. Its 56 focused local API tests and hosted checks passed. It must stay separate
from #14's approval and merge decision.

## Documentation verification

The short README keeps the previous text verbatim inside Earlier work. Its local links
resolve, and both CPU rows match raw recorded checks and scores. The screenshot is an
actual PR #14 metadata setup capture, not inference; source is in
`docs/assets/studio-model-setup.json`. The public clone/frozen sync/Studio startup path
passed on clean main in an existing Windows user, with export/restart and authored HTTP
checks: `docs/assets/quickstart-main-check.json`. It is not a fresh-profile installation.

All three interview bug stories were checked against source. Four targeted regressions
passed: stale-read recovery, missing/wrong-key HTTP status, failed-load HTTP status and
the numeric conversion false negative. No new model inference or GPU run was performed
for this convergence work. Earlier model trials remain source-bound historical evidence.

## Owner gates

Actual walkthrough, pilot and review dates are not known: the supplied [DAY]/[DATE]
values were placeholders. No reminder or timed delivery is scheduled. The pilot sheet
is prepared to forward; feedback and case-study observations remain blank.
The recruiter video/site update is a prepared storyboard, not published media.
