# Furnace — deck outline for owner review

Private draft. Numeric links bind claims to [the registry](claims.json). Notes are
for the presenter; placeholders must stay blank until the owner supplies records.

## Slide 1 — Problem

Researchers can train a model but still need a safe, repeatable way to serve it,
evaluate changes, see failures and recover the service.

Speaker notes: This is our problem hypothesis, not a customer-interview finding.
A notebook producing text is different from an evaluated service. Ask the pilot
researcher which jobs actually consume their time before claiming savings.

## Slide 2 — Why now

Open model supply is growing: Hugging Face reported [more than 2 million](sources.json "claim:hf-models")
public model repositories. Research code adds dependencies and execution risk.
See [primary evidence](why-now.md).

Speaker notes: Repositories are not customers or unique builders. A pinned engine's
inventory and custom-model code illustrate a compatibility boundary; no industry-wide
support delay or arbitrary architecture support has been measured.

## Slide 3 — Product

Free kit and Studio: inspect the model, select a recipe or supply an adapter,
explicitly prepare/start, evaluate, inspect logs and recover. Documents is an example
application using the infrastructure.

Speaker notes: Show Studio first. Verified bytes, pinned runtime, bounded execution
and retained results are the engineering product. Operated service is coming later;
local software is not a multi-tenant hosted platform.

## Slide 4 — Proof

| Provisional installed CPU journey | Quality-rule passes | Identical after relaunch |
| --- | --- | --- |
| Qwen small transformer | [11](evidence/qwen-cpu.json "claim:qwen-quality") / [12](evidence/qwen-cpu.json "claim:qwen-cases") | [12](evidence/qwen-cpu.json "claim:qwen-repeat") / [12](evidence/qwen-cpu.json "claim:qwen-cases") |
| Granite hybrid | [7](evidence/granite-cpu.json "claim:granite-quality") / [12](evidence/granite-cpu.json "claim:granite-cases") | [12](evidence/granite-cpu.json "claim:granite-repeat") / [12](evidence/granite-cpu.json "claim:granite-cases") |

Speaker notes: Same provisional installer, same developer Windows machine, cached
weights. Crashes were injected and recovery required explicit action. Identical wrong
answers remain wrong. These are engineering trials, not traction. Outside-researcher
adapter proof is pending final freeze. [Evidence scope](evidence-room.md).

## Slide 5 — Traction

[OWNER: actual consented design partners, completed sessions, repeat usage and paid
commitments, with dated records. Leave blank until observed.]

Speaker notes: Engineering validation belongs on Proof. Planned pilots are not customers;
non-binding letters are not revenue. Do not substitute GitHub activity for demand.

## Slide 6 — Customer

Start with researchers who have working checkpoints and need to share evaluated
local services. Qualify model fit, hardware, support burden and willingness to pay
through founder-assisted onboarding.

Speaker notes: Interview maintainers and labs repeating experiments. Do not assume
all researchers need a managed product. [Partner kit](design-partners.md).

## Slide 7 — Business model and unit economics

Proposed [$20/month](evidence/roadmap.md "claim:price") on customer compute; Furnace operates
the software. An illustrative shared control-plane allocation is about
[$0.50](claims.json "claim:control-per-user") per tenant before support. Furnace GPU
compute must be capped or usage-priced: the cited GPU-only rate converts to
[$0.5904](claims.json "claim:gpu-hour") per hour before other costs.

Speaker notes: Proposal, not an offer or validated willingness to pay. Support may
dominate. No unlimited GPU promise. [Inputs and exclusions](unit-economics.md).

## Slide 8 — Market

Start from identifiable projects, not a top-down AI market figure. NeurIPS reported
[5,290](sources.json "claim:accepted") accepted main-track papers: a prospecting
population, not a buyer count. [Bottom-up scenarios](market.md).

Speaker notes: Authors overlap, many papers have no serving need, payment propensity
is unknown. A narrow researcher subscription alone may be a small business. Team
expansion needs evidence; it is not an excuse to inflate today's market.

## Slide 9 — Competition

Hosted platforms already serve custom models; local runners have accessible model
interfaces; evaluation tools have deeper benchmarks. Furnace's proposed wedge is
researcher-owned adapters, a coherent local operating/evidence workflow and founder
assistance. [Primary-source comparison](competition.md).

Speaker notes: Competitors can add these features. Container boundaries are not
unique intellectual property. Users must demonstrate the switching value.

## Slide 10 — Go-to-market

Offer personal model onboarding free for candid feedback. Publish no customer story
without consent. Learn whether researchers return and labs will pay for ongoing
operation. [Outreach draft](design-partners.md).

Speaker notes: Nothing has been sent. Begin with the planned pilot. Record failures,
help and elapsed time with consent, without background telemetry.

## Slide 11 — Founder and how it is built

Dilip builds Furnace with AI coding agents, pull requests, CI, regression reproductions
and recorded model trials. [OWNER: surname, contact, experience and motivation.]

Speaker notes: The founder owns decisions and must explain the code. Agent review is
not independent human review. Distinguish tests, measurements, review and remaining gaps.

## Slide 12 — Milestones and ask

Accept the frozen release and private pilot; test an outside architecture; validate
repeat usage and support costs; then assess a managed-service experiment.
[OWNER: funding amount, instrument, runway, allocation and dates.]

Speaker notes: No fabricated fundraising target. No paid operation before approval.
Next commercial decisions depend on observed need and economics. [Inputs](owner-inputs.md).
