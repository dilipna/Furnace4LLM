# Assisted deployment pilot

Status: planned. No participant, session date, feedback or successful deployment is
claimed yet. Dilip will assist one unfamiliar friend/classmate. This is a local research
pilot, not a paid customer or production deployment.

## Forward this prerequisite sheet

- Windows with Docker Desktop installed and Linux containers enabled. The existing
  real-model records used Windows 11; another version is a pilot observation, not an
  already verified platform. Use the CPU Qwen recipe; no NVIDIA setup is required.
- Git, Python 3.12 and uv available in a fresh terminal. First installation needs network
  access for dependencies, the pinned server image and Qwen weights.
- Record RAM, free disk and Docker's CPU/memory allocation. Leave room for the model,
  images and Python environment. Preflight checks resource requests; it does not certify
  that every configuration will fit. Do not promise an unmeasured universal minimum.
- Allow model/image downloads only after reviewing the recipe and consent. This pilot
  does not purchase compute, require a payment card or provision a cloud server.
- Use sanitized example text and a dedicated workspace. Do not use private research
  code, production prompts or credentials. Keep Studio's private session link private.

Before the session, Dilip supplies the exact reviewed source SHA or ZIP and its checksum,
the applicable prerequisites and a way to contact him. Do not install an unpublished or
unreviewed release merely because its filename looks current. Preserve prior installs.

## Session sheet

Participant alias: ______  Date: ______  Artifact/source SHA: ______
OS/Python/uv/Docker versions: ______  RAM/free disk/Docker allocation: ______
Cache initially empty or populated: ______  Assistance agreed: ______
User's own goal, in their words: ______

| Task | Actual outcome / error | Help given | Evidence location |
| --- | --- | --- | --- |
| Explain Furnace's purpose before using it. | | | |
| Install the selected source/artifact and open Studio. | | | |
| Open the guided example; explain why it is not model inference. | | | |
| Create/select a project and choose the reviewed Qwen CPU recipe. | | | |
| Review prerequisites, approve preparation and explicitly start. | | | |
| Send a sanitized message and identify which server responded. | | | |
| Load the reference suite, noting that it replaces the project's cases; run checks. | | | |
| Explain a failed/unscored result and the limits of a rule score. | | | |
| Export the evidence and find its project/configuration identity. | | | |
| Stop, reopen and resume explicitly; confirm saved work survives. | | | |

Record install/download/start/request times separately if measured, including cache state
and assistance. Do not compare this session with a differently cached historical run as
a speedup. Mark omitted steps as omitted; missing results never pass.

## Feedback form — leave blank until participation

| Question | Participant's actual answer |
| --- | --- |
| What were you trying to accomplish? | |
| What did you expect Furnace to do? | |
| Where did you stop or ask for help? | |
| What did the example and model results prove? What did they not prove? | |
| Would you use it again? For what task? | |
| What one change would make it more useful? | |
| May an anonymized account of this session be shared? | |

## Case-study template

Write after the session: user goal and environment → exact attempt → what broke →
diagnosis → scoped fix → retest → what remains unresolved. Link sanitized logs and
the tested commit. Separate independent actions from assisted ones. Include failed
model answers and evaluator limitations. Obtain permission before quoting the participant;
use an alias and omit personal paths/session keys from public material.

## Owner walkthrough before the pilot

Without reading implementation, explain the purpose, distinguish the fixture from a
model, identify prerequisites, interpret an exported result and find the next action.
Record actual confusion and help. Automation does not fill in this observation sheet.

Dilip's walkthrough: **November 24, 2026**. Pilot: **November 29, 2026**;
participant confirmation pending. Review/rehearsal: **December 3, 2026**.
The owner is forwarding prerequisites and will confirm the participant by November 24.
A one-time reminder is scheduled for November 23 to send this walkthrough sheet.
These are planned sessions; all observations and participant feedback remain blank.
