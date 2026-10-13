# Guard on F2 (agent-actions-py, the second Python fixture)

Impact analysis, then the selected items executed in the sandbox. F2 is a development fixture (written by the developer agent from the plan's F2 specification); expected failures were fixed with the scenarios.

| scenario | selected | conclusion | failed | as expected |
| --- | ---: | ---: | ---: | ---: |
| f2_docs_only | security:approval_gate | success | – | yes |
| f2_r4_refund_approval_removed | unit:tests/test_tools.py, security:approval_gate | failure | security:approval_gate | yes |
| f2_email_subject | unit:tests/test_tools.py, check:prompt_prefix_stable, security:approval_gate | neutral | – | NO |
