# Proposed operation — transparent costs

Nothing provisioned or charged. [Roadmap section six](evidence/roadmap.txt) proposes
customer compute by default and capped Furnace compute for demo models, best-effort
support and retained records. Billing/accounts remain inactive.

[Modal pricing](https://modal.com/pricing), read November 27, 2026: standard T4 GPU
$0.000164/second, CPU physical core $0.0000131/second, RAM $0.00000222/GiB/second.
These standard-compute rates are not its separately priced Sandbox product. Reference
estimate, not vendor selection, quote or spending. Exclude promotional credits.

## Customer compute — illustrative shared control plane

Customer pays their hardware/cloud inference costs. Proposed $20/month covers software
operation, not free compute. The future control plane must not proxy inference
payloads to fit this resource assumption.

Assume 0.125 physical cores and 0.125 GiB continuously allocated for a 730-hour month:

`(0.125 × 0.0000131 + 0.125 × 0.00000222) × 730 × 3600 = $5.03/month` rounded.

This is a public-rate allocation, not a tested viable deployment. Add an assumed $5
monthly reserve for shared DB/backups/logs (not a supplier quote). Share across 20
hypothetical customers: `($5.03 + $5) / 20 ≈ $0.50/customer/month`.
At 1 customer the same allocation is about $10.03. Utilization matters.

Excluded: bursts, minimum durations, payment fees, tax, egress, storage overages,
signing, abuse, monitoring tools, security work and support. Assuming 15 minutes of
support monthly at $30/hour adds $7.50/customer. No gross-margin claim is justified
until those costs and willingness to pay are measured.

## Furnace compute — capped or usage-priced

GPU only: `0.000164 × 3600 = $0.5904/hour`; at 730 hours, about $430.99/month.
An illustrative 5 GPU hours costs $2.952 GPU only, not an approved cap or a model-fit
guarantee. CPU, RAM, loading/idle time, storage, egress, retries and support add cost.
At $20, GPU-only break-even is about 33.88 T4 hours before other expenses; it is not
an allowable entitlement. Larger GPUs cost more. Refuse over-cap requests or obtain
explicit usage agreement; never silent overage. [Inputs/calculations](claims.json).

Pending owner decisions: provider/region, reliability objective, resource budget,
retention, approved cap, support scope and price viability. None is needed to activate
commercial infrastructure for the December release, because none will be activated.
