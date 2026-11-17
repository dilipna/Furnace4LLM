# Bound HTTP draining before Studio cleanup — 2026-11-17

An additional warm-cache Windows ZIP verification failed after the launcher exited:
the listener/lease remained active. This result is retained in the local log
`work/simple-interface-bundle-mode-regression.log`. It does not erase the earlier
successful cold-cache run. Inspection confirmed the exact verifier-owned server
processes still existed and stderr ended at Uvicorn's shutdown stage, following a
Windows Proactor connection-reset exception. Those metadata-only test processes
were explicitly cleaned up by their verified PID tree. No unrelated process was stopped.

Do not infer that the native failure's complete cause is proven. A separate,
deterministic regression confirmed an application defect in the same unbounded
HTTP-drain phase: Studio inherited Uvicorn's unlimited graceful shutdown wait.

`apps/api/tests/test_studio_shutdown.py` launches the actual Studio server and sends
an authenticated request with an unfinished body. It leaves that client open and
requests shutdown through the same server flag set by the signal handler. Before
the fix, Studio remained alive after eight seconds and could not reach normal
lifespan cleanup. The test failed on that exact assertion. After setting
`timeout_graceful_shutdown=5`, it passed, together with 16 existing ownership/Studio
tests on Windows. It asserts the real workspace can be leased again, the incomplete
project was never saved, and the listening port closes. It does not merely assert
a returned status or constructor option. The server-constructor wrapper only
exposes the real server's shutdown flag; it does not replace network or cleanup behavior.

Only ASGI connection/task draining is bounded. Normal lifespan recovery/worker
cleanup still runs. In-flight external model generation cannot be forcibly
cancelled. The five seconds are not an end-to-end shutdown or model-latency claim.

Reproduce with `uv run pytest -q apps/api/tests/test_studio_shutdown.py`.
The newly packaged application must additionally rerun the installed Windows/Linux
journeys. Earlier ZIP receipts remain bound to their original source and archive.

The full Linux run at ancestry-only merge `dab4fc2` separately reported 618 passes
and one existing inference-client timing failure: level-16 median overhead was
2.88 ms then 2.21 ms, against the existing requirement below 2 ms. Its p95/TPOT
assertions were within bounds. Logs were inspected before attribution; the cause
has not been established and no threshold, trial count or test was changed.
The earlier identical-tree `d161ce8` run passed 619 tests plus Web/image; it is not
substituted for the failed exact-head result. New code requires fresh checks.
