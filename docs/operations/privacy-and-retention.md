# Privacy and retention (local Studio)

What Furnace stores, where, for how long, and what never leaves the machine. This describes
the local application only; a hosted service would need its own policy once it exists.

## Nothing is sent to Furnace

Studio runs on `127.0.0.1` and has no telemetry, account or analytics. Network traffic happens
only when you act: preparing a recipe downloads pinned images (container registries) and
weights (Hugging Face) over HTTPS; requests go only to a model server on this machine.
Furnace-operated model containers have no route to the internet.

## What is stored

| data | where | kept |
| --- | --- | --- |
| projects, contracts, preferences, cases and expectations | `<workspace>/studio.sqlite3` | until you edit them or remove the project |
| evaluation results: statuses, rule reasons, request IDs, durations, token counts, output **hashes** | same database | current result plus the last ten attempts per project |
| operations log: event kinds, IDs, durations, token counts, error categories | `<workspace>/logs/operations.jsonl` (+ up to 4 rotated files of 1 MiB) | entries older than the project's **log retention** setting (default 7 days) are deleted when Studio starts |
| server log tail | inside the running container only (shown on request, key redacted) | removed with the container |
| verified weights | `<artifacts>/blobs/sha256/` | until `furnace studio-cleanup --artifacts … --yes` |
| exports (kit ZIP) | wherever you save them | under your control |

## What is never stored

- Raw prompts and raw model outputs of evaluations or ad-hoc messages (the database keeps
  SHA-256 hashes; ad-hoc replies live only in the browser tab).
- The per-launch API key of a managed server (memory only; tests and every recorded
  validation run check the database, operations log and exports for it).
- Upstream error bodies from a model server (only a fixed error category).

The operations log refuses fields named `input`, `output`, `prompt`, `messages`, `content`,
`key`, `api_key` or `token`, so content cannot be added to it by mistake.

## Caveats

- Saved cases and expectations are your data and are included in exports.
- Local files are not encrypted by Furnace; rely on the operating system's disk encryption.
- Anyone with access to the Docker daemon can read container environments, including a
  running server's key; Docker access is equivalent to administrator access on most hosts.
- A researcher adapter runs your own code; what it logs inside its container is up to that code.

## Deleting data

Remove a project in Studio to delete its record and history. Delete `<workspace>` (with
Studio closed) to remove everything Studio stored; run `furnace studio-cleanup` first to
remove containers, weights and images.
