# Publish dependency caches only after successful isolated installation

Prepared PR description for local `fix/dependency-cache-recovery`, based on main.
Publication is now authorized after integration checks. Main, including #7's normal
merge `09427b15f07e23ae395225b76ce221d1919cd504`, has been merged into this branch
without conflicts or history rewriting. Fresh local/hosted results will be attached
to the PR; the older 527-test result below belongs to its explicitly named source.

A pip timeout or Docker CLI exception previously left a named dependency volume
behind. Retry accepted its existence as success and skipped installation, exposing
partial dependencies. Nonzero failure also force-removed a shared cache volume.

Each initializer now installs into a unique private candidate. Successful pip exit
and a completion marker precede atomic publication through a stopped Docker metadata
container. Readers validate the image/key/mount/marker. Concurrent callers select one
complete cache; losers only remove their own unpublished candidates without force.
An ambiguous publication acknowledgement retains the potentially published volume.
The v2 identity includes the actual image ID, requirements paths/content and entry
file; old unmarked caches are left untouched and rebuilt on first use.

Validation on executable commit `d5768c0290997becf04fa0cc66310ad08b6074f1`:

- Before-fix timeout/exception regressions demonstrated only one install on retry.
- Eight mocked orchestration cases and four real Docker regressions cover retry,
  concurrent publication, an active consumer during failure and a killed initializer.
  Tests assert actual imports, container/volume state and execution counts.
- Full local Linux Python check: 527 passed, existing Starlette/httpx warning; Ruff,
  format, import contracts, Pyright and Postgres migrations passed.
- Unmodified repository API-image check passed. The Python check used the documented
  preinstalled-Node workaround; it is local Linux verification, not hosted CI.

No dependency, service, evaluation threshold or historical measurement changes.
Concurrent initializers may duplicate installation work. Host kill/daemon outage may
leave private orphan resources requiring owner cleanup; retry does not steal them.
Published corruption fails closed. No model/GPU experiment or live GitHub execution
was tested. See [contract](../dependency-cache.md) and
[verification](002-cache-verification.md). Obtain the repository's full pre-push checks
and fresh exact-head hosted checks when publication is authorized. Keep this separate
from PR #7 and the dependent local Studio connector work.
