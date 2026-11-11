# Repair verification contract

The state/acceptance rules below were written before implementation. Tests and local
verification are required before marking the follow-up resolved.

Baseline: unmerged PR #5, exact head `d1dfad9e5a0e816cf6a38bc588c555fe196813cc`.
This branch is stacked on that head; its diff must be reviewed against that commit.

| Outcome | Functional evidence | Performance evidence | Draft proposal |
|---|---|---|---|
| `functional_only` | reproduced failure; new and existing tests pass | not requested (no endpoint/callback) | allowed only on the explicit offline path; prominently UNVERIFIED |
| `verified` | same functional requirements | complete finite interval evidence satisfies the existing repair rule | allowed with explicit consent |
| `rejected` / `repro_failed` | missing/failed, or performance required but not accepted | missing, skipped, invalid, failed, exceptional, or insufficient to decide the required repair bounds | no draft |

The existing repair rule remains: candidate-vs-head interval upper bound < 0%;
candidate-vs-base interval upper bound < 25%. The 90% interval and three-run minimum
are unchanged. An INCONCLUSIVE comparison against the separate +10% noise tolerance
can still satisfy these two repair bounds; that is not an inconclusive repair decision.

Implementation: add one terminal status, validate callback evidence rather than trusting
a truthy `within_budget`, repeat that validation at the GitHub write boundary, and expose
functional/performance verification separately in JSON and reviewer text. Measurement
exceptions fail the candidate safely. Summary-only point comparisons remain readable,
but cannot establish current interval-based repair verification.

Compatibility: consumers must recognize `functional_only`; callers that previously used
no callback, a summary-only result or a bare boolean as proof must migrate. Offline
proposals keep explicit opt-in (`--no-endpoint --open-pr`), use a distinct proposal branch
and title, and never enter the fully verified/automatic path. Historical result files are
not rewritten. No performance thresholds, dependencies or cache installation changes.

New draft branches use `furnace/repair-v2-*` or `furnace/proposal-v2-*`. This prevents
reusing legacy drafts whose body does not describe this contract or its current evidence.
Retries within a namespace are still content-addressed/idempotent. A new-contract draft
can coexist with a preexisting legacy draft; nothing closes or overwrites the old one.

JSON has separate `verification.functional` (`passed` / `not_passed`) and
`verification.performance` (`passed` / `unverified` / `not_verified`) fields. Functional
pass may be reported even when performance rejects every candidate; `rejected` still
opens nothing. A selected passing functional candidate and files are required at the
write boundary. `verified` is reserved for valid required performance evidence.

A blocking candidate comparison cannot be overridden by a passing-looking latency
interval or `within_budget=True`. The PR head may legitimately be blocked. Candidate-vs-base
PASS/WARN/INCONCLUSIVE labels are not recomputed from rounded intervals, preserving the
original repair rule at the separate +10% tolerance boundary.
