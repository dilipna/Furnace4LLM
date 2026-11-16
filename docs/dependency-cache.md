# Dependency cache completion and recovery

The old cache treated a named volume's existence as proof that pip had completed.
A timeout or CLI exception left partial dependencies reusable on retry. The regression
tests were run against that implementation first: timeout and exception cases failed
because the retry made only one install call instead of two. The nonzero-exit case
also exposed force-removal of a shared volume; that is a separate safety assertion,
not evidence of timeout reuse.

## Publication contract

`sandbox/dependency_cache.py` installs into a unique candidate volume. A completed
pip process must exit zero, then an isolated helper writes a versioned marker.
Only then does Docker atomically create a fixed-name **stopped metadata container**
with a read-only reference to that volume. Furnace never starts this container.
Readers validate its image ID, labels, mount identity and marker before reuse.

The v2 key hashes all validated requirements paths and bytes, the selected entry file
and the actual image ID. Runtime execution uses that same pinned ID. Legacy unmarked
`furnace-deps-*` volumes are left untouched and are not reused; the first v2 use
reinstalls dependencies. The old digest helper is retained for legacy identification.
An image change intentionally creates a new cache. This does not make unpinned
dependency specifications reproducible across independent installs.

Installers never share writable volumes. Two simultaneous initializers may duplicate
installation work; the daemon's unique container name chooses one complete cache.
The loser removes only its own unpublished candidate, without force-removing a volume.
Existing consumers continue using their read-only published cache. No host lock,
lock-expiry heuristic or new dependency is needed.

Timeouts and exceptions attempt to remove the caller's named installation/helper
container and staged requirements in `finally`. Failed installation cannot publish.
A publication acknowledgement timeout is ambiguous: the caller retains its candidate
because publication may have succeeded; a later reader can validate and reuse it.
Malformed published references/markers fail closed and require owner review.

## Operational boundaries

Installation retains the existing network access, resource limits, dropped
capabilities and `no-new-privileges`. It uses the image's default user (currently
root), not the runtime's uid 10001. Runtime remains nonroot, with a read-only cache
and the existing network allowlist. Cache verification helpers have no network,
a read-only root and a small resource budget. This fix does not make arbitrary pip
build code trustworthy; Docker/daemon ownership remains a trust boundary.

A killed host process or unreachable daemon can leave its private installer,
staging directory or unpublished candidate. A retry does not reuse or steal them.
Cleanup failures are logged where the process can report them. There is no automatic
garbage collector. An owner may inspect exact names/labels and container mounts,
stop only the abandoned installer, and remove only its unpublished volume without
`--force`. Do not run a global prune. Keep stopped `furnace-deps-v2-ready-*` metadata
containers: removing one loses the publication reference. Never remove a published
volume while consumers may still use it. Corruption recovery requires quiescing
affected consumers and inspecting the specific reference; Furnace does not overwrite it.

## Regression verification

```sh
uv sync --frozen
uv run pytest packages/furnace/tests/test_dependency_cache.py packages/furnace/tests/test_dependency_cache_docker.py packages/furnace/tests/test_security.py -q
```

Docker must be running. The real tests build/use the existing sandbox image and
install an authored local wheel with `--no-index`; they do not contact a package
index, execute a model or measure model performance. They verify actual container
and volume state, imports, and staged-file cleanup:

- A real interrupted installation writes partial data and times out; retry installs
  into a different volume and imports the complete package. Later reuse does not install.
- Two overlapping real initializers publish the same complete cache and remove the loser.
- A failing overlapping initializer leaves an active consumer and published cache usable.
- Killing the initializer host process leaves its private container running; retry
  succeeds independently and does not steal or select that container's partial volume.

Mocked orchestration also covers nonzero exit, CLI exceptions, ambiguous publication,
marker timeout, legacy caches, image changes and corrupt markers. New results belong
in the [verification record](follow-ups/002-cache-verification.md); historical benchmark
claims and acceptance thresholds are unchanged.
