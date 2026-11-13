# Add local researcher Studio with trustworthy fixture onboarding

Base proposal: `fix/repair-verification` while PR #6 remains open. Main is
9efc38d43e4dcb24472ceb10bb828931ec3682db; PR #5 is merged. This branch contains PR #6's
59ea54d parent plus the previously unpublished product commits through 1c22602 and this
final review. The product diff against #6 excludes the parent repair patch. No shared
history was rewritten. After #6 merges normally, retarget to main and check the new head.

Researchers previously had no downloadable workspace to inspect their projects, prepare
contracts/cases or try the surrounding infrastructure. Studio adds the free starter kit,
two local project records, inactive compute preferences, a guarded local Docker runtime
and an explicitly deterministic guided example. Python/uv are prerequisites; this is a
wheel preview, not a native installer or a provisioned $20/month service.

The example executes an uppercase fixture, compares output with a saved exact string
and leaves descriptive expectations unscored. No base/head model change, historical GPU
comparison or model inference is performed. UI and exported provenance explain the
reference, verdict, timing scope and unverified model properties. /guide separates
existing endpoint CLI adapters from the unimplemented Studio research-model path and
provides a bounded real-endpoint validation procedure without a mock fallback.

Final review reproduced a late old response replacing a newer project/configuration in
the original acceptProject implementation. Monotonic project revisions now fence state
updates. Project-bound configuration digests and protocol-versioned evidence prevent
cross-project/stale result labels; old/unbound records remain retained and unverified.
Exports include identity, source, reference and verification status. Back-cache restoration
reconfirms saved state, preserving tab drafts while withholding unconfirmed verdicts.

Validation details and exact source/artifact boundaries are in REVIEW.md and local
verification receipts. Focused tests inspect actual worker outputs/removal, persistent
revisions, exports, input invalidation and deliberately delayed response ordering. Browser
journeys cover visitor, developer and returning-user paths. Clean Linux installation
covers metadata/export/restart, not real application inference. The preinstalled-Node
Python-runner workaround is local evidence; hosted checks require pushing this PR head.

No performance threshold, historical measurement, model weight, billing/account system,
remote infrastructure or public website deployment changed. Dependency-cache recovery,
new installers and GPU experiments remain outside this PR. Human observations are blank
pending real participants; no investor/user approval is claimed.
