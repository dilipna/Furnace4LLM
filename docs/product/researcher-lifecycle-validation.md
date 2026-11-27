# Researcher lifecycle: relative cache launch fixed

A fresh Qwen2.5-0.5B CPU run found a launch defect after successful preparation.
With `--artifacts dist/researcher-lifecycle-artifacts`, verified weights reached
Docker as a relative bind-mount source. Docker rejected that path. Absolute/default
cache paths used by earlier trials had not exercised this case.

`ArtifactStore` now resolves its root once when constructed. Download, verification
and launch use the same absolute location, even if the caller later changes its
working directory. No weights, scoring rules, thresholds or model settings changed.
The validation harness also records the failed start's HTTP status/reason and stops
before attempting to inspect a nonexistent container.

## Actual before and after

| Observation | Before: `e87260f` | After: `6bb4c1e` |
| --- | --- | --- |
| Prepare images and verify weights | Passed | Passed |
| Relative cache bind source | Relative; Docker rejected it | Absolute; Docker accepted it |
| Start and connect | Failed; no inference | Ready and connected |
| Twelve-case quality rules | Not executed | **11/12 passed, 1 failed** |
| Repeated outputs / across server relaunch | Not executed | **12/12 identical / 12/12 identical** |
| Crash during evaluation | Not reached | Error recorded; no implicit retry; cleaned up |
| Hard Studio crash and reopen | Not reached | Interrupted, orphans removed, no implicit reconnect |
| Export and stop | Not reached | Manifest matched; keys omitted from application records/export; containers removed |

The failed quality case is **Reverse a word**: the model returned `tredsope`, which
failed the existing normalized rule. The same wrong output reproduced. Reproducibility
is not correctness; the overall lifecycle result is operational, not a perfect quality
score. Both evaluations and the post-restart attempt retain their rule outcomes.

Raw records, retained separately without overwriting earlier results:

- [Failed lifecycle before the fix](verification/researcher-lifecycle-2026-11-27/start-before.json)
- [Actual Docker-create rejection](verification/researcher-lifecycle-2026-11-27/mount-before.json)
- [Actual Docker-create acceptance after the fix](verification/researcher-lifecycle-2026-11-27/mount-after.json)
- [Full real-model lifecycle after the fix](verification/researcher-lifecycle-2026-11-27/lifecycle-after.json)

The successful lifecycle ran on clean source commit
`6bb4c1eab1d814ae882edcb02a90889a475581c6`. The post-fix mount-only probe ran in
the working tree before that commit; it created, then removed, a container without
executing it. It is not inference evidence.

## Reproduce

From the repository with its Python environment installed, working local Linux-container
Docker and adequate memory:

```sh
uv run --frozen python scripts/validate_managed_model.py --model qwen2.5-0.5b-instruct-q8_0 --accelerator cpu --artifacts dist/researcher-lifecycle-artifacts --port 8797 --out dist/my-new-qwen-cpu-run.json
```

Choose an unused output filename so you retain previous records. The command prepares
the pinned model, performs real inference, deliberately crashes its own model and
Studio process, restarts explicitly, exports, stops and cleans its disposable workspace.
It retains the specified weights cache. A missing cache/image requires public downloads;
this recorded run reused cached pinned weights/images and reverified the weights.

The regression in `packages/furnace/tests/test_catalog_artifacts.py` first failed
because the verified path was relative. It now exercises fetch/verify, the actual
adapter's mount specification and reuse after a working-directory change. Existing
digest mismatch, interrupted download and quarantine checks remain unchanged.

## Limits of this evidence

This is actual **CPU inference on one Windows 11 + Docker Desktop machine**, driven
through Studio's real HTTP API. It is not browser/human usability evidence, a new GPU
trial, a clean-account installation test, a new arbitrary research model, a soak test,
or hosted-service acceptance. Scripted UI/kit checks are recorded separately in the
[starter handoff](researcher-kit-handoff.md). The machine had other workloads; elapsed
times are observations, not a controlled performance comparison.

The network check probes `1.1.1.1:443` from the model's internal network. It does not
monitor every destination or prove isolation from host bridge services. Launch keys
were absent from the checked application database, logs and exports; Docker administrators
can inspect container environments while containers exist. See the
[runtime security boundary](managed-local-runtime.md#isolation-and-secrets).

The proposed $20/month Furnace-operated service remains unimplemented. No deployment,
publication, billing or main merge is included.
