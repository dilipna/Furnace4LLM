# Support (demo phase)

How researchers get help during the demo, and what to ask them for so a problem can be
reproduced without collecting their prompts, outputs or model files.

## Channel and expectations

Best-effort support by email or the contact link on the website; no service-level
agreement during the demo. Describe it that way everywhere support is mentioned.

## What to ask for

1. Studio version: the installer name (`Furnace-<version>-<commit>-windows-x64.exe`),
   the bundle file name (`furnace-studio-<version>+<commit>.zip`) or
   `git rev-parse HEAD` for a source checkout.
2. Operating system, Docker Desktop version, and for GPU problems the GPU model and driver.
3. The status line text from the model page and the **Show health, metrics and logs** output.
4. The relevant lines of `<workspace>/logs/operations.jsonl`. It contains event kinds, IDs,
   durations, token counts and error categories. Review identifying metadata before
   sharing; excluded prompt/key fields do not make every log appropriate to publish.
5. If a run looks wrong: the exported kit's `workspace-plan.json` and `serving-manifest.json`.
   These include the project's own cases and expectations; ask before requesting them.

Never ask for model weights, API keys, or raw prompts and outputs. A researcher who wants to
share a failing case can do so deliberately.

## First responses

Most issues map to a row in the [recovery runbook](recovery-runbook.md): missing Docker or
GPU runtime, memory limits, interrupted downloads, server exits, timeouts, a second Studio on
the same workspace. Reply with the matching action and the reason code.

## Escalation and records

Reproduce on the validation machine with `scripts/validate_managed_model.py` where possible.
A confirmed defect becomes a GitHub issue with the reason code, versions and a failing test;
fixes follow the normal pull-request path and the [release procedure](release-procedure.md).
Delete support material received from researchers once the issue is closed, consistent with
[privacy and retention](privacy-and-retention.md).
