# Product contract — researcher deployment gateway

Owner clarification, November 28, 2026. This defines completion; it is not a claim
that the future SaaS service is already available. The existing theme stays.

## One sentence

**Download Furnace, connect your existing model, and deploy it with serving,
security controls, evaluations, monitoring and recovery.**

Furnace is a researcher infrastructure platform. Its free local application and
starter kit are the entry point. The proposed $20/month Furnace-operated service
would operate deployments on customer or Furnace compute. Documents is an example
application using that infrastructure.

“Gateway” means the operating layer between a research model and the applications
using its served interface. It does not change the product into a cloud API aggregator.
It does not mean every checkpoint becomes runnable without model-specific code.

## What the promised journey must demonstrate

| Stage | Acceptance behavior | Current evidence / remaining gate |
| --- | --- | --- |
| Download | Install and open without requiring developer tools; explain inference prerequisites | Provisional installer exercised by developer; owner clean-account report and final acceptance pending. |
| Connect / bind | Select model project, compatible recipe or researcher adapter; preserve project/configuration identity | Kit and recipe paths exercised in candidate branch; genuine outside-researcher adapter trial pending. Metadata inspection alone is not runnable-model proof. |
| Free kit | Export assessment, missing infrastructure and configuration without pretending inspection ran the model | Existing kit path; final installed journey must exercise export. |
| Deploy locally | Explicitly prepare/start the isolated service, reach readiness and accept an actual inference request | Provisional installed Qwen/Granite CPU records linked below. No public endpoint implied. |
| Evaluate | Run stated cases, preserve actual failures and bind results to the exact model/configuration | Recorded quality and reproducibility outcomes, not universal quality guarantees. |
| Operate | Show health/resources/logs; record interruption, restart explicitly, compare outputs and stop | Developer lifecycle trials; final same-byte release and human pilot gates remain. |
| Furnace operates it | Approved remote operation, access control, deployment ownership, quotas, updates, backup/recovery and sustainable support | Proposal only, on customer or Furnace compute. Not delivered by the local supervisor alone. |

A recipe supports its pinned model/runtime. An existing-server connector uses a
compatible server; it does not give Furnace ownership of that external server's
lifecycle. A custom Python adapter needs researcher loading/generation code and a
pinned dependency image. Python-adapter code identity is content-digested, while its
weights inventory is names/sizes, not a verified content hash. Never generalize the
recipe's verified-weight claim to that path.

## Completion and order

The December 4 delivery remains the local MVP plus private demonstration. Rebuild one
final installer and accept the Studio/model journey and document example on those
exact bytes. Keep recorded demonstrations, deterministic fixtures and live inference
separate. The [pilot sheets](https://github.com/dilipna/Furnace4LLM/tree/ca9d9d9b4c915bd5f6d0256e1fd2b2366e0b3d10/docs/operations/pilot-2026-11-29)
collect actual observations; none may be filled from automation.

After final candidate freeze, run the timeboxed [outside-architecture proof](adapter-proof.md)
without changing Furnace. Record incompatibility rather than claiming arbitrary support.
The future managed service needs a separate approved milestone; no billing, accounts,
internet-facing deployment, spending or publication is authorized by this clarification.
A new caption is not completion of the product contract.

[Evidence scopes and raw trials](evidence-room.md). [Proposal snapshot](evidence/roadmap.txt).
[Limitations](known-limitations.md). The contract records the intended end-to-end
behavior without changing the frozen application or presenting proposals as features.
