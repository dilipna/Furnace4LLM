# Furnace Studio: 90-second demo script

Status: **draft, not recorded or published**. Dilip records after the November 24
walkthrough and review. This script contains no new execution results.

## Before recording

- Choose a reviewed source commit after the merge decisions. Record `git rev-parse HEAD`
  and `git status --short`; identify any local edits. Start Studio with
  `uv run furnace studio --workspace <dedicated-demo-workspace>`.
- Use Windows with Docker Desktop/Linux containers and the pinned Qwen2.5-0.5B CPU
  recipe. Confirm the recipe's license, resource requests and download consent.
  Record Docker/Python/uv versions, available resources and whether assets are cached.
- Open a dedicated project. The guided example may supply metadata, but its fixture
  is not the model. On **Connect a local model server**, use **Let Furnace run a pinned
  model**, select Qwen and save the selection. Do not record session URLs or keys.
- Rehearse a completed reference batch, a separate crash batch and a restart batch
  without changing model, cases or configuration between them. Export each outcome;
  keep failed/unscored cases. The first completed batch is the comparison reference.
- In a second terminal, identify the exact demo model container with
  `docker ps --filter label=furnace.managed.role=model`. In Docker Desktop, inspect its
  labels: `furnace.managed.project` and `furnace.managed.workspace` must match this
  demo project/workspace; `furnace.managed.role` must be `model`. Keep the verified
  container ID ready. Never target the relay or an unrelated container.

## Cut and narration

These are **editing timeboxes**, not measured install/start/evaluation durations.
Keep a visible “Recorded local demo” caption. Label every time cut and actual cache
state; preserve the full source recording and raw evidence separately.

| Time | Screen/action | Spoken words |
| --- | --- | --- |
| 0–10 s | Studio; select pinned Qwen CPU recipe. | “Furnace takes a supported open-weight model and provides its local serving, evaluations, logs and recovery. Here I’m selecting Qwen in Studio.” |
| 10–22 s | Review resource requests and consent; **Prepare (download and verify)**. Show verified state; label elapsed-time cut/cache state. | “I approve preparation. Furnace pulls the pinned image and checks the weights by SHA-256. This edit skips waiting; the caption shows whether the assets were cached.” |
| 22–32 s | **Start server**; wait for ready; show health/metrics. | “Start is a separate action. The model runs in a non-root, read-only container on an internal network. Studio connects only when it is ready.” |
| 32–47 s | **Load reference suite**, acknowledging replacement of project cases; **Run endpoint cases**. Show a completed baseline and an actual failed/unscored result if present. | “These are real model requests. The reference suite uses bounded rules, not a semantic judge. A failed answer stays visible.” |
| 47–61 s | Start a second batch; while it is running, kill the verified model container. Show interrupted batch/error and failed server state. | “Now I deliberately kill this model server during evaluation. Furnace records the interruption and keeps partial results. It does not silently restart or call the interrupted batch successful.” |
| 61–78 s | **Start server** explicitly; wait for ready; **Run endpoint cases** again with identical configuration. | “I restart explicitly and rerun the same cases. The earlier interrupted attempt remains in history.” |
| 78–90 s | Show actual reproducibility count/reference and export. | “Here is the actual output comparison with the completed attempt before the crash. Identical text means reproducibility, not correctness. The export retains the configuration, results and failures.” |

Use the live count and status shown in the recording; do not prefill “12/12 identical.”
If outputs differ, show the difference. If no comparable completed reference exists,
say so and complete that step before claiming a comparison across launches.

## Crash choreography for rehearsal

While the second evaluation is **running**, execute
`docker kill <verified-model-container-id>` in the second terminal, replacing the
placeholder with the inspected ID. This intentionally terminates only the model
process; keep Studio open. Show the interrupted evaluation's error and the server's
failed state. If the batch finished before the kill, it is not a mid-evaluation crash:
retain that take as such and repeat the sequence honestly. Do not alter timeouts,
scoring thresholds or expected answers to manufacture the desired outcome.

After **Start server** and a completed rerun, the UI's reproducibility line should
identify a completed reference from an earlier launch with the same configuration.
Keep that reference visible; a same-launch repeat alone does not demonstrate recovery.
This choreography follows [the existing validation procedure](../../scripts/validate_managed_model.py)
and [the recovery runbook](recovery-runbook.md); it has not been newly executed for
this draft. Rehearse on the chosen build before recording.

## Recording receipt — fill only after execution

| Field | Actual observation |
| --- | --- |
| Recording date and source commit; dirty status | |
| OS, hardware, Docker/Python/uv versions | |
| Recipe, accelerator and cache state | |
| Uncut preparation/start/evaluation/restart durations | |
| Baseline run ID and launch ID | |
| Crash run ID, error and launch ID | |
| Restart run ID, launch ID, comparison reference and actual count | |
| Export/evidence location; retained failed/unscored cases | |
| Cuts, omitted steps or unexpected outcomes | |

Stop the demo server after capturing evidence. Have Dilip review the cut before
requesting separate publication approval. This local recording does not make the
public website a live model service. The hosted service and subscription remain proposals.
