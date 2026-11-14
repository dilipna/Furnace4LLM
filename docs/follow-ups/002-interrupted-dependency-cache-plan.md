# Next reliability step: dependency-cache initialization (not implemented)

Dependency: [open issue 002](002-interrupted-dependency-cache.md). The repair-verification
patch does not modify `docker_sandbox.py` or its cache installation behavior.

Proposed bounded design:

1. Use a versioned cache namespace, incorporating requirements content **and** the sandbox
   image identity. Existing unmarked volumes cannot prove successful installation; do not
   silently trust or delete them. Document that old volumes become unused and can be removed
   by their owner after checking consumers.
2. Publish a successful-initialization marker only after pip exits zero, including the
   exact key/image/protocol. Mere volume existence is insufficient. Run consumers with
   read-only mounts only after that validated marker exists.
3. Serialize initialization per key using a host lock appropriate to the supported runner
   filesystem (a protocol for shared/multiple runner hosts must be explicit). Recheck the
   marker under the lock. Prefer a unique staging volume and atomic publication/selection
   of a completed cache, so readers never observe pip's partial writes. Evaluate Docker
   volume naming/publication limitations before choosing the exact on-disk pointer.
4. Give install containers explicit unique names. In a `finally` path remove staged files
   and terminate/remove **only that invocation's** container on timeout/exception. On nonzero
   exit preserve a bounded scrubbed diagnostic, discard only its unpublished staging data,
   and allow a genuine retry. No global pruning, force-removal of a published cache, or
   deletion of another initializer's volume.
5. Resolve crashes/stale ownership separately from a slow live initializer. Do not steal
   a lock based solely on elapsed installation time. Completed immutable volumes remain
   safe for concurrent consumers; garbage collection requires evidence of ownership and
   absence of users and can be a later, separately reviewed operation.

Real-Docker acceptance test, with no external packages or inference: create a tiny local
test package whose build/install script waits on a test-controlled signal. Start initializer
A, induce a bounded timeout, confirm its named container is gone and no ready marker exists,
then retry B with the signal released. Import the installed package in the real runtime
sandbox and assert the expected value. Run two initializers for the same key plus a reader:
the reader must either wait/refuse before publication or import the complete package; never
read a partial install. Verify an already active consumer is not disrupted by another
failed initializer. Assert resource cleanup and actual install invocation counts.

Also test ordinary nonzero pip exit, subprocess exception, process kill before publication,
successful cache reuse without reinstall, identity/image mismatch and an unmarked legacy
volume. Existing sandbox UID/network/capability tests must still pass. No new service or
dependency is justified until these local locking/publication requirements demand it.

This plan is a proposal. Cross-host lock semantics and atomic cache publication are design
questions to resolve during implementation, not controls claimed to exist today.
