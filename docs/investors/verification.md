# Verification performed November 27, 2026

## Actual local checks

- `python docs/investors/check_evidence.py`: passed offline byte hashes, raw JSON
  pointers, headline calculations, deck/memo numbers and investor-authored local links.
- `python docs/investors/test_check_evidence.py`: nine tests passed. Mutations include
  changed raw bytes/value, uncited number, false displayed value, wrong evidence target,
  broken file/anchor, wrong calculation, cyclic inputs and unsourced external value.
- Ruff check and format check on `docs/investors`: passed with the repository's Ruff.
- Explicit Pyright check of the new verifier and regression script: zero errors.
  The first explicit check found two optional-match typing gaps; explicit rejection
  branches resolved them before this result. Product type-check scope is unchanged.
- `git diff --check`: passed before commit.
- Offline checker and nine tests passed again from a fresh `git archive` of committed
  files, confirming copied byte hashes survive extraction without local workspace state.

## Live-source verification — incomplete, retained failure

`python docs/investors/check_evidence.py --online` exited 1. The NeurIPS program-chair
article returns HTTP 200 bot-challenge content to local urllib. The checker rejected
that response, then could not validate its live excerpt. All other attempted primary
source/provenance URLs and source excerpts completed without a reported failure.
The browser research tool separately displayed the NeurIPS article and its quoted
paper count. That manual read does not turn the automated failure into a pass.
The source registry records this retrieval-method distinction. Do not weaken or
skip this check to claim fully verified live citations. Recheck before external sharing.

## Scope

No Furnace product code, dependency, CI threshold, release artifact or app interface
changed. No new model inference, outside-adapter proof, demand measurement or human
session was executed for this investor branch. Its new verifier/tests are run explicitly;
the repository's existing pytest testpaths do not automatically discover them.
There is no claim that adding this directory adds a hosted CI gate. The PR's ordinary
hosted checks will be reported separately after it is opened.

The initial costing draft failed arithmetic validation and was corrected: allocated
control plane approximately $5.03/month, hypothetical shared allocation approximately
$0.50/user/month before support. This is still an assumption-based estimate.
