# Integration and release handoff — 2026-11-16

This is a review checklist, not a release announcement. No deployment, release,
new paid service, learned inference or new GPU experiment was performed.

## Integration state verified

- PR #5, #6 and [#7](https://github.com/dilipna/Furnace4LLM/pull/7) are merged.
  Current main is `09427b15f07e23ae395225b76ce221d1919cd504`, #7's normal merge.
  The owner explicitly authorized integration on 2026-11-16. Before merge, #7's
  unchanged `bdbedca5add63bd1778e8bdeec540f3cc14dbbbd` head had all four checks
  successful, no submitted reviews or review threads, and no new correctness blocker.
- Exact-head hosted checks are successful: Python, Web (including Studio state tests)
  and API image in [CI](https://github.com/dilipna/Furnace4LLM/actions/runs/43572672946);
  saved measurements in [evidence](https://github.com/dilipna/Furnace4LLM/actions/runs/43572672904).
  These checks belong to #7. The follow-up PRs have their own checks below.
- [PR #9](https://github.com/dilipna/Furnace4LLM/pull/9), `product/local-model-endpoint`,
  is a child of #7. It adds the optional local
  text-chat connector, bounded evaluation history, safe case-suite import and
  verification. It is not part of #7 or available on the public website.
- `improve/visitor-journeys` is preserved clean at
  `07ccfff90f025b9452a603be0a517c20deeefcef`. It concerns the public Next.js website,
  while Studio is a local application. Its parent dependency (#6) is now on main;
  it still needs its own integration review/checks before publication.
- The independent `fix/dependency-cache-recovery` branch is based on main and has
  its own contract/tests. It is not bundled into the Studio branch or PR #7.
  Executable/test commit `d5768c0290997becf04fa0cc66310ad08b6074f1` passed 527
  local Linux Python tests plus lint/types/imports/migrations and API image build/import.
  Its branch contains the before/after record and prepared PR description under
  `docs/follow-ups/002-cache-*`. The Python run uses the same documented Node
  workaround; its results must not be added to Studio's different-branch test count.

## Published follow-up checkpoint

- [PR #8](https://github.com/dilipna/Furnace4LLM/pull/8) is a draft at
  `b004e7f228bdd92bf1670b6a3018a6158c4a0c04`. Its four hosted checks passed: Python
  reported 576 passed/1 skipped; Web included 12 state tests; image and evidence passed.
- PR #9's earlier `481f5da9ff015252ef9787527eea99549673e9ba` head passed all four
  hosted checks: Python 600 passed/1 skipped and Web 18 state tests. Those results
  do not certify subsequent corrections on this branch.
- Review subsequently fixed database initialization preceding workspace ownership
  and corrected CI's moving-HEAD archive/pass-stamp race. Their before/after evidence
  is in [workspace ownership](../product/workspace-ownership-verification.md) and
  [CI identity](ci-commit-identity.md). Fresh exact-head results are recorded in PR #9.
- A separate local `integration/local-release` worktree combines both PRs without
  rewriting either branch. It does not merge them into main or deploy either UI.
- Native Windows picker automation stopped because the computer-use helper could not
  determine Chrome's current URL confidently enough to enforce policy. No browser
  input occurred. Native picker selection and human comprehension remain unverified.

## Local preview and practical review

From the `Furnace-local-model` worktree, with Python 3.12 and uv installed:

```powershell
uv sync --frozen
uv run furnace studio --no-browser
```

Open the private session link printed in the terminal; never include its token in
feedback. Keep the terminal open and use Ctrl+C to stop. No Docker, Postgres, GPU or
model is required for metadata, configuration and kit export. Docker with a local
Linux engine is required for the deterministic fixture. A separately operated,
unauthenticated `http://127.0.0.1:PORT/v1` text-chat server is required for the connector.
Neither fixture nor authored connector test responses establish model quality.

Use [participant tasks](onboarding/HUMAN_TEST.md). The owner can perform the first
session; a second unfamiliar developer remains useful for independent setup feedback.
Leave observations blank until participation. Do not require a nontechnical person
to install Docker. Label facilitator operation or explanation as assisted observation.

## Remaining gates in order

1. Completed: merge #7 after exact-head verification, preserving ancestry.
2. Completed: publish the connector as draft #9. Scoped review corrections require
   fresh local pre-push and exact-head hosted checks after each update.
3. Completed: publish the independent cache fix as draft #8. Neither follow-up PR is
   being merged in this operation. Combined local execution is a separate verification
   gate, not evidence that either draft has been merged or deployed.
4. Run the [smallest fresh-profile onboarding test](../product/native-windows-verification.md#remaining-release-gates)
   and collect actual owner/developer comprehension feedback. Assess native file-picker
   interaction; automated file injection is insufficient for that claim.
5. Select one consented model/server for a bounded compatibility trial. Record model,
   license, server version, resources, reference outputs, actual requests and failures.
   Do not infer architecture support or semantic quality from the fixture/HTTP mocks.
6. Integrate the public visitor-journey branch separately, retain recorded-only public
   hosting, and request deployment authorization only after the reviewable artifacts
   and checks are ready. Studio work is not a public-site deployment.

The managed $20/month offering, billing, hosted compute and signed native installers
remain future product work requiring operating/cost/security decisions. This local
preview does not fulfill an end-to-end managed infrastructure subscription. No money
was spent and no such service was advertised as running by these changes.

## Evidence boundaries

Application source `64798eb7d33e30cf779b7064e3b2b9231d42e1a1` passed 596 local Linux
Python tests plus lint/types/imports/migrations; see
[case-import verification](../product/case-suite-import-verification.md). The installed
preview and [new Windows/Linux receipts](../product/native-windows-verification.md)
refer to that clean application ZIP. Later verifier/documentation commits do not
change executable application code. Windows first install/start took 121.56 seconds;
this is installation overhead, not TTFT. Historical saved measurements retain their
original provenance and were not regenerated as new model-performance evidence.

Integration review subsequently reproduced and corrected malformed upstream Unicode
leaving endpoint evaluations running. That executable change and its new clean ZIP,
native Windows and Linux Chromium receipts are recorded in
[connector integration verification](../product/connector-integration-verification.md).
The older application/ZIP results above remain historical; fresh exact-head pre-push
and hosted checks are required for the corrected branch. Main's post-merge CI and
saved-evidence workflows also passed at `09427b15f07e23ae395225b76ce221d1919cd504`.
