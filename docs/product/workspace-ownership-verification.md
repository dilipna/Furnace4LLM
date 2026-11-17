# Workspace initialization ownership — 2026-11-16

Review of the combined #8/#9 application found that `create_app()` initialized
`studio.sqlite3` before the application lifespan acquired `WorkspaceLease`.
A second application could create/read the database and change its permissions
despite being refused ownership later. An owner-controlled invalid database raised
a SQLite error before the ownership refusal. This violated the documented one-owner
startup boundary; it was not evidence of model execution or a measured data-loss incident.

Three actual-file/OS-lock regressions failed before the fix:

- Constructing an application against a busy new workspace created its database.
- Constructing one against a busy invalid database opened it before checking ownership.
- Invalid-database failure happened during construction rather than owned startup.

`Store` construction now only retains its database path. Initialization runs inside
the lifespan's workspace lease, before either recovery service. A refused launch does
not open/initialize the database. A genuine initialization failure still propagates,
preserves the database bytes and releases the lease. No corruption is silently repaired
and no existing data is deleted. Session rotation and worker/evaluation recovery are
unchanged. ASGI hosts must run the application lifespan, as the supplied launcher does.

The old metadata tests instantiated `TestClient` without entering it, bypassing
lifespan and OS ownership. Their fixture now uses the real lifespan. Restart coverage
closes the first owner before opening the second and checks complete saved state and
old-token refusal. Existing export, activity privacy, model-folder preservation,
validation and removal assertions remain exercised.

## Windows crash-regression correction

An existing external-kill lease test failed once after the startup correction. A
separate diagnostic with actual Windows process handles confirmed that the venv
launcher and interpreter have different PIDs: in three trials, launcher wait returned
before the interpreter's exit was signaled. All interpreters exited within the
three-second diagnostic bound. This is not a new application crash or proof that an
active interpreter's lock should be stolen.

The crash test now calls `os._exit(17)` inside the interpreter after acquiring the
lease, and checks its exit code plus ownership announcement before reacquiring it.
This bypasses Python context-manager/finalizer cleanup and exercises OS lock release
without assuming that killing the launcher synchronously terminates its child.
The existing separate-process live-owner rejection test remains unchanged.

The focused metadata/onboarding/identity/import/real-HTTP suite passed 56 tests after
the startup change. Final affected/full checks and exact commits are recorded with
the [local integration handoff](../release/simple-interface-review.md), separately from earlier results. No learned
inference, GPU experiment, fresh-profile installation or human observation is claimed.
