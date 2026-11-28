# Distribution notice omission — reproduced and corrected

November 28, 2026. This is a packaging correction, not a legal/compliance approval.
The repository's existing MIT notice is unchanged. [Log hashes](logs.json) address
the original uncompressed output; gzip retains the before/after failures verbatim.

## Confirmed omission

Before this fix (source e08730a), `scripts/build_windows.py` copied the Python runtime,
icon, requirements and wheels but not the root Furnace `LICENSE`. Its Inno input is
that staged tree. `scripts/build_studio_bundle.py` likewise wrote wheels, requirements,
launcher, README and manifest without the root notice.

Inspected local historical staging from source 1ad2a99 had no app-root `LICENSE`;
its three workspace wheels contained no notice files. This corroborates the builder
inspection; it is not a fresh inspection of the already uninstalled 9598d6d candidate.
Do not claim a full third-party audit from those observations.

New artifact assertions exercised the actual builder staging and ZIP writing:
[before log](before.txt.gz), exit 1, three failures (one native stage, two existing ZIP
version scenarios). Compiler, dependency installation and signing were stubbed in
that native unit test; no real EXE was built by it. The version tests still execute
the extracted launcher with the declared wheel names.

## Change

- Native builder copies the unchanged root notice to `app/LICENSE` before compilation.
- Developer ZIP builder includes the same bytes as archive-root `LICENSE`.
- Native regression checks the staged file and that the separate runtime notice remains.
- Existing ZIP/version regressions check exact notice bytes inside the real ZIP.
- Existing installed-browser smoke now refuses a missing/stale installed notice, so
  the hosted Windows build checks the installed result, not only source code.

[After log](after.txt.gz): 16 focused tests passed, including the existing source/version,
wheel-integrity, stale-input and Windows artifact checks. Ruff/format and explicit
script type checks are run separately; hosted results belong to their exact head.

## Review still needed

The final source must be rebuilt and both real-model journeys accepted on its exact
new bytes. Old model/installer records do not establish acceptance of the corrected
build. No provisional binary, old acceptance record or source licence was overwritten.
The compiler/signature stubs are not native-build evidence; the ordinary Windows CI
must pass its actual build/install/smoke check.

Owner distribution review remains open: dependency/runtime notices, model-download
licences, draft policies, unsigned-preview disclosure and human install/retention.
This fix supplies Furnace's own notice; it does not certify all redistribution terms.
No model weights are added, no signing service is configured and nothing is published.

Reproduce the focused tests from the repository's installed developer environment:

```powershell
.venv/Scripts/python.exe -m pytest -q packages/furnace/tests/test_windows_build_notices.py packages/furnace/tests/test_studio_bundle_version.py packages/furnace/tests/test_windows_release.py packages/furnace/tests/test_release_package.py
```
