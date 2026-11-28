# Furnace: infrastructure around the research model

Private investment discussion draft. Product and customer hypotheses are not traction.

Model researchers already do the difficult work of building and training models.
Turning that work into a service adds packaging dependencies, serving safely,
evaluating changes, understanding failures and recovering without losing the record.
Furnace aims to make that workflow accessible without building a platform team.

The product starts with a free infrastructure kit and local Studio. A researcher
inspects their model, selects a pinned recipe or supplies a Python adapter, starts
an isolated service through explicit approvals, evaluates it, examines logs and
restarts after failure. A document assistant demonstrates an end-user workload on
this infrastructure; it is not the market definition. Furnace-operated software on
customer or Furnace compute is a proposed [$20/month](evidence/roadmap.txt "claim:price") next
step, not an available subscription.

The engineering evidence is concrete but narrow. On a provisional installed Windows
build, the small Qwen model passed [11](evidence/qwen-cpu.json "claim:qwen-quality")
of [12](evidence/qwen-cpu.json "claim:qwen-cases") quality rules; the Granite hybrid
passed [7](evidence/granite-cpu.json "claim:granite-quality"). Qwen reproduced
[12](evidence/qwen-cpu.json "claim:qwen-repeat") of [12](evidence/qwen-cpu.json "claim:qwen-cases")
outputs across relaunches; Granite also reproduced [12](evidence/granite-cpu.json "claim:granite-repeat")
of [12](evidence/granite-cpu.json "claim:granite-cases"). Crashes and explicit recovery were exercised. Correctness
and reproducibility are separate: wrong answers repeated too. These developer trials
used cached weights on the same machine, not a customer installation or an arbitrary
new architecture. [Records and limits](evidence-room.md).

Open model supply, custom research code and reproducibility expectations make the
problem timely. Existing hosted platforms and local runners are strong alternatives;
Furnace must earn adoption through the complete researcher workflow and personal
onboarding. The first customer hypothesis is a researcher with a working checkpoint
who needs repeatable local deployment. The [market scenario](market.md) is deliberately
small and labelled; model repositories and papers are not unique paying users.

The business must separate operation from compute. Customer compute avoids reselling
expensive inference as an unlimited subscription. The illustrative shared control-plane
allocation is about [$0.50](claims.json "claim:control-per-user") per customer monthly
before support and excluded expenses. Furnace-supplied GPUs require caps or usage
pricing. Neither price nor margins have been validated.

[OWNER: actual pilot observations, partners, repeat usage and paid commitments.]
Near-term milestones are the accepted release, founder-assisted deployment and
outside-researcher adapter proof. Expansion to labs and private-model teams depends
on repeated use and operational needs. [OWNER: founder biography, funding ask, use
of funds and runway.] No traction or fundraising amount is asserted.
[Known limitations](known-limitations.md).
