# Final installed acceptance — consistency check

November 28, 2026. Run this after final-source integration, rebuilding and actually
executing both journeys on the exact installer. This does not run a model, create
observations, establish customer comprehension or authorize publication.

## Why this check exists

The release procedure requires matching installer bytes and both installed journeys.
Comparing only source commit strings can overlook another build of that commit, stale
records, skipped cases or contradictory success labels. The new standard-library
`scripts/check_installed_acceptance.py` checks the file's size/SHA-256 and expected
source, installation receipts, embedded build time/version/runtime/wheel identities,
actual Studio case counts and output/restart comparisons, interruption/cleanup,
document suite digest/case coverage/receipts, and the browser's measured outputs and
stopped-model refusal. It requires the corrected installed project-notice check.

It preserves quality failures and reports their actual totals. It introduces no new
benchmark quality threshold and does not rescore outputs. The browser's existing
four task rules must pass; inference/privacy checks are not semantic-quality proof.
Records are trusted observations, not cryptographic attestation. Fabricated records
could fool a consistency checker; raw-record authorship and review remain important.

## Final evidence inputs

Put the actual new records under a dedicated directory. Copy the JSON input index
below into that directory, adjusting only filenames to the new outputs. All references
must stay under its directory. Do not edit an old run's model/build/hash to make it fit.
Keep all failed attempts separately. The installed smoke command, Studio model validator
and document validator/browser acceptance commands are described in
[Windows operations](../operations/windows-download.md) and the
[executed document procedure](installer-verification/candidate-9598d6d/document-2026-11-28/README.md).

```json
{
  "schema": "furnace-installed-acceptance-inputs-v1",
  "studio_install": "install-studio.json",
  "document_install": "install-documents.json",
  "smoke": "installed-smoke.json",
  "qwen": "qwen-cpu.json",
  "granite": "granite-cpu.json",
  "document_suite": "everyday-cpu.json",
  "document_ui": "browser/record.json",
  "suite": "suite.json"
}
```

The install receipts record actual installer exit code, source_commit and full
installer_sha256 as in the executed QA receipts; they must come from installing the
chosen file. Embedded build information comes from installed `build.json`, not from
relabeling the harness checkout. Archive the exact packaged suite bytes addressed by
its recorded digest. Never substitute a newly normalized/reformatted suite.

```powershell
.venv/Scripts/python.exe scripts/check_installed_acceptance.py --metadata PATH_TO_INSTALLER_JSON --installer PATH_TO_EXE --records PATH_TO_NEW_INPUTS_JSON --expected-commit FULL_FINAL_SOURCE_SHA
```

Success is `machine_evidence_consistent`, with retained quality totals,
`human_gates: not assessed`, and `publication_authorized: false`. Exit 1 and
`status: blocked` mean the records do not satisfy the check. Do not silence the exit
or remove unfavorable cases. The script checks the exact chosen CPU journey for
Qwen/Granite Studio and Qwen2.5-1.5B documents; it is not arbitrary-model validation.

## Actual validation performed

Eighteen focused checker regressions passed; together with relevant packaging tests,
34 tests passed locally. Positive fixtures use authored metadata around historical
record shapes and do not claim new inference or a new installer acceptance.
Tests retain Qwen/Granite/document quality failures and refuse stale source, changed
binary, another build at the same source, missing cases, forged totals, wrong installer
bindings, invalid crash/restart, missing notice/export, absent browser requests,
changed outputs, failed task rules and non-finite JSON.

[Recorded read-only controls](final-acceptance-controls.json) use the actual 9598d6d
installer and untouched raw records:

- Expected source ebdd5f2: exit 1, installer source differs from expected commit.
- Expected source 9598d6d: exit 1, missing `project_notice_matches_source` in its
  historical smoke record. This predates the corrected packaging check. The old
  execution evidence stays valid for its stated scope, not final-release readiness.

The [historical input index](installer-verification/candidate-9598d6d/acceptance-inputs.json)
points at existing records without changing them. No current final-source installer
has passed this checker; that requires the remaining integration and execution gates.

## Integration preflight — preview only

Pairwise merge-tree previews on November 28 used child #20 at d05a555, #15 at b5c16a9
and #16 at fde1eda. #15 applied without conflicts. #16 conflicted only in root
`.gitattributes`: retain the font byte-preservation rule together with every current
model/evaluation/license evidence byte-preservation rule. Do not choose one side
blindly or normalize archived evidence bytes. These previews created no branch merge
or main update and do not prove the complete future sequence; recompute with actual
heads after the owner's clean-account report, and test the resolved integrated tree.

Owner's clean-account result, pilot, distribution review and separate approval naming
the final hash remain required as recorded in [the release ledger](researcher-delivery.md).
