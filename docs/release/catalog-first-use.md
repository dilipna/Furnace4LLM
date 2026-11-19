# Recipe discovery before Docker setup

The MVP onboarding review reproduced three catalog failures at `e52e9cf`:

- With no Docker executable, `GET /api/managed/catalog` returned HTTP 500.
- With an unavailable daemon, image availability was reported as false instead of unknown.
- If inspection timed out after an initial successful daemon probe, the catalog returned 500.

All three regressions failed before the correction. Browsing a recipe is a read-only
first-use operation; it must remain distinct from preparing images/weights or running a model.

The catalog now checks readiness first, skips unavailable inspection and retains `null`
for unconfirmed image availability. An inspection exception updates Docker's unavailable
state while preserving the recipe metadata. Project records and the preparation queue
remain empty in the tests. No execution boundary, permission or consent was relaxed.

The new regressions and existing managed lifecycle suite passed: **14 tests**, one existing
Starlette warning. Installed verification now requests the actual catalog with Docker
excluded from the child PATH. Browser verification no longer replaces image inspection
with a successful false value that masked this gap. Earlier installation receipts tested
metadata/export/connector behavior without asserting catalog discovery; they are not
relabelled as evidence for the new assertion.

Studio's preview text also now distinguishes metadata inspection from supported managed
model execution, and states Docker requirements for both the fixture and managed models.
Hosted checks and new installed execution must be tied to the resulting source head.
This is a scoped correction to draft PR #13, not a deployment or permission to merge it.
