# Local Linux verification observations — 2026-11-27

These records concern the developer verification runner, not model quality or a
new release artifact. No tests were skipped or acceptance thresholds changed.

Owner decision for the December 4 release: **hosted Ubuntu CI is accepted as the
Linux gate; do not change Docker Desktop settings**. The local limitation below is
retained as a diagnostic and is not relabeled successful or required to be resolved
by changing this machine for that release.

- [Node bootstrap observation](node-bootstrap-observed.txt): a fresh Pyright 1.1.414
  invocation in the existing Python/uv Linux image succeeded and installed Node
  26.13.1. The older `0-alpha` bootstrap failure did not reproduce. The runner now
  supplies Node 24 explicitly, matching hosted CI, and includes the previously
  omitted download and everyday-selection JavaScript tests.
- [First full attempt](first-attempt-2a4fb2a.log.gz), source `2a4fb2a`: **not a pass**.
  It was interrupted after 4 failures, 709 passes and 1 skip. One failure was the
  orchestration fixture incorrectly interpreting a new Dockerfile as a tar archive;
  that fixture was fixed without changing its three initial-commit archive/pass-stamp
  assertions. The other three were serving readiness timeouts on nested loopback.
- [Positive-control loopback probe](loopback-probe.json): the temporary server was
  running, and Windows reached it with HTTP 200. Both bridge and host container clients
  got connection refused. No source, model or user-data mount was involved. This is
  the observed networking blocker; no global Docker setting was modified or guessed.
- [Child web run](child-web-7336d28.log.gz): the local Linux web job passed at exact
  source `7336d28`, including the additional test suites. This is not a complete local
  Python/image pass or real inference evidence.

The updated Python runner uses the daemon's host network and a dynamically assigned,
loopback-only PostgreSQL port, as needed to match the loopback serving tests on native
Linux. Before downloading dependencies or running tests, it verifies connectivity.
If unavailable, it exits with an actionable message and writes no pass stamp; it never
changes product endpoint security or silently omits the serving tests.

The existing commit-identity regression now exercises both reachable and unreachable
preflight outcomes. Success still requires three actual Git archives from the initial
commit even when HEAD moves. Failure requires no later jobs and no success stamp.

`bash scripts/ci_linux.sh python` must be rerun on a suitable Linux/host-networking
environment to close the local Python gate. `web` and `image` can run independently.
Hosted Ubuntu CI and native Windows suites remain separately identified evidence.
