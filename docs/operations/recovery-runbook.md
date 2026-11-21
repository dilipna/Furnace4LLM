# Recovery runbook (local Studio)

What to do when something goes wrong with a local Studio workspace or a Furnace-operated
model server. Every step below is behaviour that exists and is tested; nothing here restarts
a server or reruns an evaluation without an explicit action.

## Find out what state you are in

1. Open Studio (`uv run furnace studio`) and the model page (`/model`). The status line under
   **Let Furnace run a pinned model** names the state: `prepared`, `ready`, `stopped`,
   `failed: <reason>`, `interrupted` or `unknown`.
2. **Show health, metrics and logs** gives the container state, resources, server counters,
   recent operations (no prompts or outputs) and a server log tail with the key redacted.
3. The operations log is `<workspace>/logs/operations.jsonl` (one JSON object per line). Search
   it by `project_id`, `run_id` or `request_id`.
4. List what Docker still holds for the workspace without changing anything:
   `uv run furnace studio-cleanup --workspace <workspace>` (dry run).

## Symptoms and actions

| symptom | cause | action |
| --- | --- | --- |
| `failed: server_out_of_memory` | the server exceeded its container memory | raise **Container memory** or lower **Context tokens**, then **Start server** |
| `failed: server_exited_<code>` | the server process exited (137 usually means it was killed) | read the log tail, then **Start server**; the interrupted evaluation keeps its recorded cases and shows `error` for the case in flight |
| `failed: server_load_timeout` / `server_load_failed` | weights did not load in time, or the server reported a load error | check the log tail; for an adapter, check its `load()`; start again |
| `failed: artifact_digest_mismatch` | stored weights no longer match their pinned SHA-256 | the file was quarantined under `<artifacts>/quarantine/`; **Prepare** again to download a verified copy |
| `failed: download_cancelled` or a download error | preparation was interrupted | **Prepare** again: the partial file resumes and is never used until verified |
| `interrupted` after reopening Studio | the previous Studio session ended while a server ran; its containers were removed on startup | **Start server** explicitly; reconnecting happens automatically on ready |
| `unknown` | cleanup could not be confirmed (Docker was unreachable) | start Docker Desktop, reopen Studio (cleanup is retried), or press **Stop server**; reconfiguring is refused until cleanup is confirmed |
| `docker_unavailable`, `gpu_runtime_unavailable`, `memory_exceeds_docker_limit` | preflight refused | follow the message; see the preflight table in the [runtime contract](../product/managed-local-runtime.md#preflight-checks) |
| evaluation stops with `endpoint_timeout` | one request exceeded its timeout | raise the request timeout or lower tokens per request; reconnect or restart; retry re-executes every case |
| "This Studio workspace is already open" | a second Studio on the same workspace | use the running one, or close it; after a crash the lock is released by the operating system |

## After a crash of Studio itself

1. Reopen Studio on the same workspace before deleting anything. Startup marks running
   evaluations `interrupted` (their recorded cases are kept), removes every container and
   network labelled for the workspace, and never reconnects or reruns on its own.
2. If Docker was down at that moment, the launch is `unknown`; start Docker and reopen again.
3. Start the server explicitly and rerun the evaluation if you need a complete result.
   Reproducibility compares the new run with the previous completed one of the same
   configuration.

## Remove everything Furnace started

```sh
uv run furnace studio-cleanup --workspace <workspace> --yes
uv run furnace studio-cleanup --workspace <workspace> --artifacts <artifacts> --images --yes
```

The first removes containers and networks; the second also deletes verified weights and the
pinned images. Neither touches model folders, project files or exports. Studio must be closed.

## What is not covered

There is no automatic restart, alerting or remote monitoring, and no hosted service to fail
over to. The recovery behaviour above is verified on Windows 11 with Docker Desktop; see
[real-model validation](../product/real-model-validation.md).
