# Researcher product review — actual results blank

Purpose: verify the owner-defined model-infrastructure product in the current theme.
This is separate from the original November 24 walkthrough. No human participation
or approval is recorded here.

## Review the local website

Open http://127.0.0.1:4011 while the preview server runs. To restart an already-built
preview from this checkout: `python scripts/preview_site.py --port 4011`.
An installer and any real footage must be staged from actual completed builds/runs.
The site is recorded-only and is not deployed by this checklist.

Without reading implementation details, answer:

1. Who is Furnace for, and what problem does it address?
2. What can you do with the free application and starter kit today?
3. Does the $20/month offer operate today? Who would operate the proposed infrastructure?
4. Is the demonstration live, recorded model execution or a deterministic fixture?
5. Where does the document assistant fit?
6. Find requirements, the download and the next action for your model.

| Participant | Purpose understood | Free/proposed distinction | Demo understood | Next action | Assistance / confusion |
| --- | --- | --- | --- | --- | --- |
| Owner | | | | | |
| Unfamiliar researcher | | | | | |

Record actual words and mistakes. Mark guided observations assisted. Browser
automation does not establish comprehension.

## Smallest clean-account application test

Prerequisites: Windows x64 test account, approved unsigned preview, a verified
installer checksum and a small non-sensitive model-project folder. No developer
tools, GPU or Docker are required for the first inspection/export task.

1. Install and open Furnace; confirm researcher Studio is the default.
2. Add the project folder. Explain the assessment's limits: metadata was inspected,
   not imported, trained or evaluated.
3. Download the free starter kit through the UI and open the ZIP.
4. Find the model-connection workspace and its execution prerequisites.
5. Quit the app, reopen the saved project and confirm its identity/settings.
6. Exercise uninstall retention/deletion choices only in the agreed test account.

Expected outcome: the app opens without Python/Git/uv, inspects the chosen project,
exports a readable kit and keeps the proposed service separate from local functionality.
Actual SmartScreen, independent-account and interactive deletion observations still
require a person. Scripted CI installation is separate evidence.

| Step | Actual result | Error / assistance |
| --- | --- | --- |
| Install / open | | |
| Inspect project | | |
| Export / inspect ZIP | | |
| Connection prerequisites | | |
| Quit / reopen identity | | |
| Retention / deletion | | |

Optional real-model task: with Docker Linux containers, suitable memory and an approved
recipe/adapter, prepare/start explicitly, ask, evaluate, inspect logs/health and recover
from an agreed stopped server. Record failed answers and interruptions. Do not expose
the local API publicly or use private customer data in the initial demonstration.

Remaining managed-service gates: operator host choice, invited-user access design,
resource limits, exposed-surface security review, backup/recovery verification and
explicit deployment/spending approval. Hosted operation and billing are not implemented.
