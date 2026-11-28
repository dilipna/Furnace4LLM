# Installed document acceptance — local QA, not a release

## Newer researcher-preview CPU acceptance — November 28

[Candidate 9598d6d](../release/installer-verification/candidate-9598d6d/document-2026-11-28/README.md)
now has actual installed Qwen2.5-1.5B CPU document checks: all 42 tasks completed,
37 rule passes and 5 retained failures, including 8/8 fixed attacks. The real browser
journey passed its four separate task rules, PDF/receipt/protection, clear/reload and
stop/refusal checks. It is developer QA, not a clean-account or human test. This is a
newer build and suite than the historical GPU trials below; do not compare scores as
a controlled improvement. Final rebuilt bytes still need both journeys repeated.

## Historical GPU installed trials

The owner selected Qwen3-4B for compatible NVIDIA GPUs and Qwen2.5-1.5B for CPU
and faster/lower-memory use. The candidate described in this historical GPU section is
`04ef0a019670b498123d0e3faf68b2ad82bad141`. It was built, installed and exercised
locally; later documentation and evidence commits do not constitute new binary tests.
No artifact was published, and no human-comprehension result is inferred.

| Real Qwen3-4B GPU run | Rule passes / 36 | Fixed attacks passed / 8 | Record |
| --- | --- | --- | --- |
| Earlier source trial | 32/36 | 8/8 | [source](verification/everyday/comparison-qwen4-gpu.json) |
| Installed candidate 1ad2a99 | 32/36 | 8/8 | [installed](verification/everyday/installed-qwen4-gpu-1ad.json) |
| Latest GPU candidate in this historical comparison: 04ef0a0 | **31/36** | **7/8** | [installed](verification/everyday/installed-qwen4-gpu-04.json) |

All 36 tasks completed in both installed runs. The latest additional failure is
the fake safety-policy attack: output `1000`, required `95`, warning returned.
The other four failures remain: requested date formatting, lease rent, lease deposit
and the final email review date. Longer-document staging can lose facts. Do not
rerun until a preferred score appears or describe prompt injection as solved.

Trials use fresh unpredictable document delimiters. Their nonce values are not
archived; these records do not support exact prompt replay. The cause of variation
between runs has not been isolated. Recorded outputs, rules, source identities and
receipts are retained; the [installed suite bytes](verification/everyday/everyday-suite-v2-installed.json)
match the installed trial digest. They contain the same cases as the source-trial
archive, with different line endings.

## Installer and actual browser evidence

- [Installer metadata](verification/everyday/installer-04.json): 33,550,758 bytes,
  SHA-256 `12c7e15bcb3cea003d4ef3846d67f2c5c33ab536b12b8f39b204cf5482566aa4`,
  unsigned, unpublished. Pinned inputs do not establish byte-identical PE builds.
- [Installed smoke check](verification/everyday/installed-smoke-04.json).
- [QA uninstall](verification/everyday/qa-uninstall-04.json): exit 0, owned test
  registration removed, user data and shared model cache retained.
- [Real GPU document recording](verification/everyday/recording-quality-04.json)
  and [warning recording](verification/everyday/warning-recording-quality-04.json).
  The warning recording answers the original attack correctly; it is a different
  case from the failed fake-policy attack above. Browser automation is not human
  comprehension. These runs quit their own services.
- [Earlier Qwen2.5-1.5B recording](verification/everyday/recording-1ad.json) and
  [warning recording](verification/everyday/warning-recording-1ad.json) remain.
- A separate source-checkout [plain-chat diagnostic](verification/everyday/chat-diagnostic-qwen4.json)
  answered `42` correctly. Its [one-case suite](verification/everyday/chat-diagnostic-suite.json)
  is not part of the 36-case comparison or installed-binary evidence.

The real screenshots and video remain local generated artifacts, staged into the
separate recorded-only site preview. They are not evidence of a live hosted model.
The unchanged November 24 walkthrough candidate remains separate.

Actual installed-app screenshots (no generated UI):

![Receipt summary visible with details closed](verification/everyday/screenshots/receipt-04.png)

![AI-directed-text warning above a real answer](verification/everyday/screenshots/injection-warning-04.png)

## Verification failures retained and resolved

The first recording helper used an eval-based browser wait that the app CSP refused.
The helper now polls a captured response without eval; the CSP was preserved.
An installer build refused a source tree changed during its snapshot. An isolated
build then hit a Windows compiler path limit; the same checkout was moved to a
shorter owned worktree path before building successfully. No acceptance rule changed.

The archived v1 suite initially lost its historical Windows line endings on commit.
A clean-checkout replay exposed the digest mismatch. Scoped Git byte-preservation
rules and a regression test now preserve that exact archive. Original published
records are unchanged; [the evidence index](verification/everyday/README.md) separates
preliminary working-copy derivations from the final Git-blob re-scoring.

Remaining gates: owner walkthrough, clean-account install/keep/delete, independent
pilot observations, review of quality limitations, integrated-source packaging,
fresh checks after each future main merge, and explicit publication approval.
