# Onboarding milestone review — 2026-11-14

Code/package source: **34748999f5f0b14b0cefbf09cd38af05b4562f80** on
`product/researcher-starter`. A following documentation-only commit records this handoff.
Artifact package version: **0.1.0** (preview); identify this build by source/hash, not version
alone. ZIP SHA256: `43fcdc36c3a1bcaa9e1d98a7052a3ed6bb801cb0cc53224015f597358aff8909`. Source manifest records `source_dirty: false`.

## Branch and dependencies

Started from reported clean head 1c22602. That head already contained the free local
inventory/starter-kit CLI, Studio UI/SQLite project records, inactive compute preferences,
model contracts/cases, Docker framework runtime/recovery/lease, downloadable wheel bundle,
guided example, environment checks, draft/output isolation and prior verification docs.
It did not contain a real Studio model adapter, active billing or hosted infrastructure.

GitHub metadata and remote refs were checked again on 2026-11-14. PR #5 is merged normally
at main 9efc38d43e4dcb24472ceb10bb828931ec3682db. PR #6 is still OPEN, head
59ea54dcf3df7ea9deab2bb11ae66b8e3fa9f777. That commit is this branch's ancestor; the
product branch is not on origin. Proposed draft PR base is `fix/repair-verification`, so
its parent repair patch is not duplicated. After #6 merges normally, retarget to main.
No merge, push, rewrite, release/tag, deployment or publication occurred. The independent
repair-verification and visitor-journeys worktrees remain unchanged and clean.

## Truthfulness trace

UI example button → authenticated POST /api/examples/framework → packaged metadata,
contract and two cases; no Docker/model execution. Explicit adapter selection/consent →
POST start → actual isolated Linux Docker worker. Evaluate → bounded predict calls →
exact-string comparison for one case and unscored descriptive expectation for the other.
Results are persisted with run ID, time, project, configuration and protocol identity.
Opening/reopening the page reads that saved evidence; it does not execute a new run.

| Part | Evidence category and meaning |
| --- | --- |
| Bundled project and cases | Authored synthetic inputs/expectations, not measured results |
| Fixture output | Newly executed deterministic uppercase function; no learned model |
| Pass/fail | Exact output versus saved expected string. No base/head code/model change is compared |
| Baseline/reference | Expected string supplied by author, not an earlier measured model baseline |
| Timing | Actual worker round trip including Docker control, not model latency/GPU performance |
| Historical GPU measurements | Separate saved experiment files, not imported into this example or altered |
| Newly executed model inference | None for this milestone |
| Next action | /guide gives compatibility status and exact real-endpoint smoke requirements |

These limits are stated before start, beside results, per-request timings and in exported
workspace-plan.json provenance/README. Saved results show their time and say reopening
will not rerun. Exported runtime state is a snapshot, not a live readiness guarantee.

## Confirmed fixes and focused evidence

The original 1c22602 acceptProject function was replayed with synthetic out-of-order
response objects: a late revision 2 replaced known revision 4 and restored its old
completed label/configuration. This was frontend-function execution, not inference.
Monotonic stored revisions and merge guards now reject older/unknown-project responses.
Tests deliberately resolve an earlier response after newer state and assert the state
itself stays current; another project's state and deleted records cannot be overwritten.

Protocol framework-v2 binds evidence to project ID, contract, plan and canonical case
inputs/expectations. API tests check actual digest changes, SQLite revisions and exports;
real-worker tests check outputs, run/request IDs, container removal, input invalidation
and report provenance. Legacy/unbound records are retained, with recorded labels preserved,
but do not verify the new project/configuration. Old unfavorable evidence is not relabeled
successful. No performance threshold or recorded benchmark was changed.

Browser returning-user checks changed the contract through the app API while the browser
was on /guide. Back navigation showed zero passes/two not_run cases. A prior downloaded
report retained its original project/configuration, as a snapshot should. Draft A survived
refresh and switching to B; B's notes were empty and returning to A restored its draft.
Saving/reloading did not restore an old current verdict. Back-cache restoration code
withholds unconfirmed evidence and permits navigation/refresh; whether this particular
browser used BFCache rather than a fresh document was not conclusively observed.

## Verification boundaries

- Focused Windows API/onboarding/runtime/identity suite: **19 passed**, one existing
  Starlette/httpx warning. Node state suite: **12 passed**. CLI real-endpoint flags/help
  were checked against the implementation; no model endpoint was called.
- Required local Linux jobs at exact code source 3474899: **561 non-GPU Python tests
  passed**, one existing warning; Ruff/format/import contracts/Pyright/migrations passed.
  Web builds, range/prefix/12 Studio tests, static export and API image build/import passed.
- Initial 14abaee Linux run failed at two builder lint findings because a formatting step
  moved a narrow subprocess annotation. The two-line correction in 3474899 passed the
  unchanged lint rules. That failure was inspected and is not reported as a pass.
- Python verification used the existing local preinstalled-Node image
  furnace-review-toolchain:repair-verification, image ID
  sha256:19c7bf233149fffa6c35ebc3d0847b47672352cc129cce88ba6d6fb4d5414df4.
  Only the Python runner image reference differs from scripts/ci_linux.sh; committed-tree
  staging, uid 1001, Postgres, dependencies, migrations, test selection and assertions are
  unchanged. Historical stock-run nodeenv bootstrap failed parsing '0-alpha'; the stock
  Python runner was not rerun or relabeled successful. Hosted CI for this unpublished
  branch remains pending an authorized push. Old PR #6 checks do not verify this branch.

## Exact clean-install scope

Installed the ZIP/hash above in Debian GNU/Linux 12 (bookworm), Python 3.12.12 and uv
0.9.30, using ghcr.io/astral-sh/uv@sha256:85d4cb1afa769a7338e095b927bee941cf5ec92266c7424b3f6c0f2748567248.
The outer Docker test ran as uid 10001 with a read-only root and empty tmpfs uv cache.
Only the built ZIP and verification script were mounted; the checkout and Docker socket
were not. The app ran in a temporary extracted directory and installed its wheels/pinned
public-registry dependencies. No Docker CLI exists in that image.

Executed: build_studio_bundle.py; python /verify.py /bundle.zip --expect-empty-cache;
launcher missing-uv check; installed launch.py --no-browser with temporary workspace/port;
real loopback HTTP project/example creation, contract edit, kit-byte/provenance inspection,
module/guide asset checks, normal stop/relaunch, persistence and old-token rejection,
record removal. Receipts identify source/hash and the workflow. Registry access occurred
for installation. No model inference, GitHub product operation or remote model service
occurred inside this test. Audit-only GitHub metadata/ref reads were separate.

**Interface starts / metadata-guided kit workflow succeeds** is established by the clean
container. **Fixture example executes** is separately established by real Docker/browser
and runtime integration checks. **Real application/model evaluation succeeds** is not
established. These results are not native Windows/macOS clean-install certification.

## Browser observations — automated, no participants

Collected 2026-11-13 on the local source preview, desktop and 390px phone viewport:
- Visitor opened example, saw missing-consent error, started actual worker, ran checks,
  saw one exact pass/one unscored case and downloaded a six-file kit with matching IDs.
- Developer found header /guide, read implemented/tested/planned paths, inspected local
  environment checks, and found the bounded real-endpoint command/reference prerequisites.
- Returning-user actions exercised project switch, draft restore, status refresh, Back
  after server-side invalidation and reload without reviving old passes.
- Loading buttons were observed (checking, starting, running); consent error text was
  observed. Keyboard Tab from Model contract focused Infrastructure. Phone app and guide
  had no horizontal overflow (scrollWidth 375, innerWidth 390). This is not a full
  accessibility audit or a claim that humans understood it.

Screenshots/receipts are in the curated local review packet. The temporary browser tab
was closed during continuation; its screenshots remain. The phone viewport override was
cleared, review workers confirmed absent and saved review metadata retained.

## Real-model status and release gates

Studio real-model path: **not implemented/validated**. Fixture path: implemented/tested.
Existing furnace-bench endpoint adapters: implemented; historical pinned vLLM evidence
exists for Qwen/Qwen2.5-0.5B-Instruct revision
7ae557604adf67be50417f59c2c2f167def9a775, separate from this milestone. A current user's
endpoint/model combination remains untested. Native custom-architecture loading in Studio
is planned. No identified running Furnace inference server was found; no model weights
were fetched and no mock substituted. /guide supplies one exact four-request endpoint
smoke (one warmup, three measured requests) requiring an authorized pinned server and
separately verified author-reference output. CLI exit zero alone does not establish success.

Blocking next actions: authorization to push/open the prepared draft PR; hosted checks
on its actual head; parent #6 integration before main merge. Human feedback, fresh
Windows/macOS onboarding and broader BFCache/accessibility checks remain required before
claims in those areas. The five-task two-person sheet remains blank. A real-model support
claim remains blocked by the missing Studio adapter/current endpoint validation.
Billing, accounts, hosted compute, Kubernetes, cache recovery, a new installer, new GPU
experiments and public website deployment are outside this operation. No paid/free-hosting
constraint changed. See PR.md and CHECKLIST.md for the exact proposed source publication.
