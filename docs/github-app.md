# GitHub App setup and the live demo (about 20 minutes)

Furnace talks to GitHub only through a GitHub App. Every job mints a token scoped to one
repository and only the permissions it needs; Furnace opens **draft** pull requests and
check runs, never merges, and never pushes to a default branch.

## 1. Create the App (once)

GitHub → Settings → Developer settings → GitHub Apps → **New GitHub App**.

| field | value |
|---|---|
| GitHub App name | `furnace-dev-<your-username>` (must be globally unique) |
| Homepage URL | `http://localhost:3100` |
| Webhook | **uncheck "Active"** (the runner CLI calls GitHub; no public URL needed) |
| Repository permissions | **Checks: Read and write** · **Contents: Read and write** · **Pull requests: Read and write** · Metadata: Read-only (automatic) |
| Account permissions | none |
| Where can this GitHub App be installed? | Only on this account |

Click **Create GitHub App**. On the next page:

1. Note the **App ID** (a number near the top).
2. Under "Private keys", click **Generate a private key**. A `.pem` file downloads. Move it
   outside the repository, e.g. `C:\Users\<you>\.furnace\github-app.pem`. Never commit it.

## 2. Create the demo repository and install the App

```bash
# a new PRIVATE repository on GitHub named furnace-demo-f1 (empty, no README), then:
git clone https://github.com/<you>/furnace-demo-f1 C:/dev/furnace-demo-f1
cd C:/dev/furnace
uv run python scripts/demo_repo.py init C:/dev/furnace-demo-f1
cd C:/dev/furnace-demo-f1 && git add -A && git commit -m "Kilnworks support assistant" && git push -u origin main
```

App settings page → **Install App** → your account → **Only select repositories** →
`furnace-demo-f1` → Install.

## 3. Configure the runner

Add to `C:\dev\furnace\.env` (git-ignored):

```
FURNACE_GITHUB_APP_ID=<the App ID>
FURNACE_GITHUB_PRIVATE_KEY_PATH=C:/Users/<you>/.furnace/github-app.pem
```

Check it (prints the App name, its permissions and the installation):

```bash
uv run furnace gh-check
```

## 4. The demo, end to end

Prerequisites: Docker Desktop running; lab vLLM up
(`HF_HOME_HOST=... docker compose --profile gpu up -d vllm`); laptop on AC power.

```bash
cd C:/dev/furnace
Q=fixtures/apps/support-rag-py/docs/facts.json

# Forge: plan + sandbox-validate, then open a draft PR with the reliability layer
uv run furnace gh-forge <you>/furnace-demo-f1 --questions $Q \
    --workload bench/results/2026-10-04-f1-quality/workload-f1-traces-qwen05b.yaml --open-pr

# A regression PR: the exact R1 change FurnaceBench measured
cd C:/dev/furnace-demo-f1 && git checkout -b add-request-tracing
uv run --project C:/dev/furnace python C:/dev/furnace/scripts/demo_repo.py apply . r1_dynamic_head
git commit -am "Add request id and timestamp to the system prompt for debugging" && git push -u origin add-request-tracing
# open the PR on GitHub (base: main), note its number N

# Guard: targeted checks -> a check run on the PR (expect a failure with the perf table)
cd C:/dev/furnace
uv run furnace gh-guard <you>/furnace-demo-f1 N --suite fixtures/scenarios/f1_suite.py --questions $Q --max-prompt-tokens 3840

# Repair: regression test first, sandbox validation, perf gate -> draft PR into the PR branch
uv run furnace gh-repair <you>/furnace-demo-f1 N --suite fixtures/scenarios/f1_suite.py --questions $Q --open-pr
```

Without `--open-pr`, Forge and repair run as a dry run and print what they would change.

## Notes

- PRs from forks are refused by default: their code would run in the sandbox.
- The suite file (`fixtures/scenarios/f1_suite.py`) binds F1's checks to graph nodes; for
  another repository, write a suite file with the same `SuiteItem` shape.
- Webhook-driven runs (Guard on every push) need a public URL (e.g. smee.io) and the
  `FURNACE_GITHUB_WEBHOOK_SECRET` setting; the CLI path above does not.
