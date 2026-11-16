# Add an explicit local-server connection and reusable evaluation suites

Prepared description for a future draft PR from `product/local-model-endpoint`.
Do not attach this to #7: it describes its dependent child changes. No push or PR
creation has been performed for this branch.

Researchers can connect Studio to an already running loopback text-chat server,
explicitly consent to bounded requests, inspect failure/retry evidence and export a
configuration-bound kit. The connector accepts only literal local HTTP addresses,
does not follow redirects/use proxies/resolve arbitrary hosts, and has no credential
entry. It does not download weights, start model servers or provision infrastructure.

Evaluation history retains the ten latest attempts, including failures. Reuse requires
matching project/configuration identity; reopening a workspace disconnects the endpoint
and preserves evidence rather than executing it again. History stores metadata/hashes,
not raw response text. Optional bounded JSONL import previews cases before explicit
replacement, strips imported verdict labels, and rejects a stale configuration inside
the project lock. Import and export make no inference calls.

Validation:

- Clean application `64798eb` passed 596 local Linux Python tests, lint, formatting,
  import boundaries, types and real Postgres migrations. The runner uses the documented
  preinstalled-Node workaround; this is local Linux evidence, not hosted CI.
- 18 parser/state tests passed on Windows and Linux Node 24. API image build/import
  passed at `83b0e9a` (same application source).
- Installed Chromium tests cover delayed responses/import reads, project identity,
  stale replacement, history, explicit retries, exports and restart/token rotation.
- Native Windows installed API verification passed with an empty cache and existing
  user/Python/uv. Linux installed verification also passed after verifier changes.
  Both used ZIP SHA-256 `405ad1c75b46a8022d0eb67078c60e7f454cd444e993e4abe52889e9f53f28bf`.

Authored HTTP responses are test fixtures, not learned inference. No new GPU run,
real model/server compatibility trial, fresh Windows profile, macOS onboarding,
native file-picker test or human comprehension result is claimed. Human observation
tables remain blank. Historical acceptance rules and measured results are unchanged.

The public website remains separate and recorded-only. Billing, hosted compute,
installers and dependency-cache recovery are outside this change. Obtain exact-head
hosted checks after publication and keep the PR a draft until its review gates are
assessed. Full scope/evidence: [current handoff](current-review.md),
[connector guide](../product/local-model-endpoint.md),
[case import](../product/case-suite-import.md), and
[Windows verification](../product/native-windows-verification.md).
