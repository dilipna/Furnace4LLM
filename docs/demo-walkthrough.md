# Recruiter demo: recording plan

Status: storyboard prepared; final video and public-site update are not published.
The owner's recording script is [the 90-second Studio demo](operations/demo-script-90s.md).
Use that script for narration and crash/restart choreography; this page describes
the recorded-only public-site handoff.
Use the reviewed candidate after its merge decision. Stay on the existing recorded-only
site at a zero hosting budget. A public visitor must not start a server or submit a prompt
to Dilip's machine. Recorded steps and any interactive navigation must be labelled.

## Captioned walkthrough target

The following timeboxes are editing targets, not measured setup times. Model preparation
may take much longer on a fresh machine; label cuts and whether assets were cached.

| Segment | What to show | What to say |
| --- | --- | --- |
| 0–10 seconds | Studio and the selected Qwen recipe | Infrastructure around a supported research model; local preview. |
| 10–25 seconds | Pinned revision, resources and explicit prepare/start controls | User controls downloads and execution. Disclose cached assets. |
| 25–40 seconds | A real sanitized request and response | This is recorded model inference, not the deterministic fixture. |
| 40–60 seconds | Reference cases, score and a failed case | Rule checks are not semantic quality. Keep the failure visible. |
| 60–80 seconds | A scoped failure, retained attempt and explicit recovery | No hidden retry; reopening and readiness are separate from verification. |
| 80–90 seconds | Export, source and limitations | One machine; link raw evidence and installation prerequisites. |

Show only steps that actually ran. If a segment is omitted, say so. Do not substitute
an HTTP test server or generated animation for model inference. Avoid session URLs,
API keys, personal file paths and private prompts in footage.

## Release gate

1. Select the approved source and record the environment, cache state and raw run.
2. Prepare the captioned video locally and check it against that record.
3. Ask Dilip to review the cut and approve publication explicitly.
4. Only then update the existing site's front door; keep earlier Guard demonstrations
   under Earlier work and preserve their measurements.

Browser checks can establish that navigation/playback works. Recruiter comprehension
still needs an actual person to explain the purpose, recording status and limitations.
