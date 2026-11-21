# Hosted managed service for the first demo models — design proposal

Status: **proposal for owner review**. Nothing here is built, provisioned or paid for. It
describes how the local components that already work would become a hosted service for one
or two demo models, and which owner decisions it waits on.

## What already exists and carries over

| local component (verified) | role in the hosted service |
| --- | --- |
| pinned recipes and serving manifests (`runtime/catalog.py`) | the only models the service will run; each deployment cites a manifest digest |
| verified artifact store (`runtime/artifacts.py`) | populates each host's weights cache; refuses unverified bytes |
| supervisor (`runtime/serving.py`) | runs one isolated model container per tenant deployment on a host |
| adapter contract and Python host | the path for a customer's own architecture later |
| rule-scored evaluations, reproducibility, operations log | per-tenant evaluation history and audit trail |
| recovery semantics (explicit restart, orphan cleanup) | host agent behaviour after crashes and restarts |

## Proposed shape for the demo (one or two models, invited researchers)

1. **One GPU host** (owner-operated machine or a single cloud GPU instance) running Docker and
   a small **host agent**: the supervisor plus an HTTPS API. Studio's per-project service
   becomes the agent's per-tenant service.
2. **Control plane** (small web service plus database): accounts, API tokens, which tenant
   owns which deployment, usage counters and plan limits. It never sees model outputs.
3. **Ingress**: TLS terminating proxy in front of the agent. Each request carries the
   tenant's token; the proxy forwards to that tenant's relay. The per-launch model key stays
   inside the host, as locally.
4. **Isolation**: the local container policy (non-root, read-only root, internal network, no
   egress, memory/CPU/PID limits) per tenant, plus one internal network per tenant, plus a
   per-tenant request quota. Shared GPU means tenants share hardware; for the demo, run one
   tenant per model at a time or accept time-sliced sharing and say so.
5. **Storage and backups**: weights are reproducible from pinned sources (no backup needed,
   only the verified cache). Back up the control-plane database and per-tenant evaluation
   records daily, with restore tested.
6. **Updates**: a new recipe or engine version is a new manifest; deploy side by side, run the
   reference suite on the host, switch tenants explicitly. Runs keep citing the manifest they
   used.
7. **Recovery drill** (to demonstrate before inviting anyone): kill the model container,
   reboot the host, restore the database from backup, and show that every deployment comes
   back `interrupted`, restarts explicitly and reproduces its last evaluation.

## Work items once decided

- Host agent API (start, stop, status, evaluate, observe) with token authentication.
- Control plane with accounts, tenants, tokens, plan limits and usage metering (billing
  stays off until approved).
- Per-tenant networks and quotas; refusal at limits, never silent overage.
- TLS ingress, health checks, alerting on `failed`/`unknown` states.
- Backup and restore, documented and exercised.
- Security review of the exposed surface before any external user.

## Decisions needed from the owner

1. **Hosting**: owner-operated GPU machine or which cloud provider and region.
2. **Spending limit** per month for the demo.
3. **Who gets access** (recommendation: a handful of invited researchers).
4. **Which model(s)** to host first (recommendation: Qwen2.5 0.5B; Granite 4.0 H 350M as the
   non-transformer example) and whether GPU sharing between tenants is acceptable.
5. **Plan limits** for the $20/month offer (see the proposal in
   [roadmap-status.md](roadmap-status.md#6-subscription--proposal-billing-and-accounts-inactive)).

Cost depends entirely on decision 1 and is not estimated here.
