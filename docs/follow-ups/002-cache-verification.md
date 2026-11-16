# Dependency-cache recovery verification — 2026-11-16

Tested application/test commit: `d5768c0290997becf04fa0cc66310ad08b6074f1`.
Base: main `d4c92cfb453a79582896404849654ae7c18ee1a7`.
Branch: local `fix/dependency-cache-recovery`; no push, PR, merge or deployment.
Later documentation-only commits do not change the tested executable code.

## Before and after

The new failure regressions were first run against the old `_deps_volume` control
flow. Timeout and CLI-exception cases failed the install-count assertion: retry
returned the precreated volume after only one installation attempt. The nonzero-exit
case separately failed the assertion forbidding force-removal of a shared volume.
The original mocked reproduction remains in [issue 002](002-interrupted-dependency-cache.md).

After the fix, the focused cache/security suite passed **57 tests** in the local
Windows development working tree. This included eight mocked orchestration cases
and four real Docker tests. The final committed-tree Linux run below includes these
same tests and the existing queue, Guard, repair and sandbox checks.

The real Docker cases do actual offline pip installation of an authored tiny wheel,
not just returned-status checks. Assertions inspect named containers, volumes,
installation attempts, staged paths and imports from the nonroot sandbox:

1. Partial installation plus real CLI timeout: installer removed, no published
   reference, staging removed; retry uses a new volume and imports the complete
   package. A subsequent call reuses it without another candidate/install.
2. Two overlapping installations: both complete privately, both callers select the
   same published cache, and only the winning volume remains.
3. Overlapping failure with an active consumer: the failed initializer cannot
   remove/mutate the published cache; the running consumer imports successfully.
4. Killed host initializer: its paused container/partial volume remain private while
   retry completes independently; retry does not steal or reuse the abandoned work.
   The test then removes its exact owned resources.

Ambiguous publication acknowledgement, marker timeout and CLI exception are mocked
failure injection; they are not claimed as real daemon-outage experiments. The
killed-process test intentionally demonstrates the documented orphan limitation.

## Final committed-tree Linux checks

| Check | Result |
| --- | --- |
| Ruff check and format | Passed; 400 files formatted |
| Import boundaries | Both contracts passed |
| Pyright | 0 errors, 0 warnings |
| Real Postgres 17 migrations | Passed through `b3f1c2d4e5a6` |
| All configured non-GPU Python tests | **527 passed in 281.32 s** |
| Warning | One existing Starlette/httpx deprecation warning |
| API image build and `furnace_api.main` import | Passed via unchanged `scripts/ci_linux.sh image` |

These are **local Linux container** results, not hosted GitHub CI. The Python run
archives committed HEAD, runs as uid 1001, and uses the real Docker daemon and
Postgres. It used the previously documented preinstalled-Node workaround: only the
Python runner image was replaced, from
`ghcr.io/astral-sh/uv:python3.12-bookworm` to the existing local
`furnace-review-toolchain:repair-verification`. That image copies Node 24 from
`node:24-bookworm` onto the same uv base. The prior unmodified runner failed during
Pyright/nodeenv bootstrap with `ValueError: invalid literal for int() with base 10:
'0-alpha'`; it is not reclassified as a pass. No test selection, assertion, evaluation
threshold or repository workflow was weakened.

To reproduce the workaround from PowerShell with the documented image already built:

```powershell
$cacheCi = (Get-Content scripts/ci_linux.sh -Raw).Replace('ghcr.io/astral-sh/uv:python3.12-bookworm bash', 'furnace-review-toolchain:repair-verification bash')
[IO.File]::WriteAllText((Join-Path (Split-Path $pwd) 'ci_cache_linux_node.sh'), $cacheCi, [Text.UTF8Encoding]::new($false))
& 'C:/Program Files/Git/bin/bash.exe' ../ci_cache_linux_node.sh python
& 'C:/Program Files/Git/bin/bash.exe' scripts/ci_linux.sh image
```

Raw local logs remain in the enclosing task workspace's `work/cache-linux-python.log`
and `work/cache-linux-image.log`; the commands and results above are committed so
review does not depend on those local files. Public-site builds were not rerun for
this sandbox-only patch. Fresh hosted checks remain required after an authorized push.

No live GitHub write workflow, model inference, GPU test or new performance experiment
was run. Historical measurements and acceptance rules remain unchanged. The
[cache contract](../dependency-cache.md) documents v2 migration, duplicate concurrent
work, stopped reference containers, and owner cleanup after process/daemon failure.
