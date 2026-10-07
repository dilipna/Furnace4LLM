# RQ3: impact-aware selection vs the full suite

13 PR scenarios on F1, 8-item suite, lab vLLM (Qwen2.5-0.5B) on the laptop GPU. Ground truth = FAIL verdicts of the full suite on that scenario.

| metric | full suite | targeted |
| --- | ---: | ---: |
| suite items executed | 100% | 46% |
| wall time (s, all scenarios) | 964 | 502 |
| endpoint-busy time (s) | 839 | 444 |
| judge tokens (cost-model estimate; judge not run) | 1,560,000 | 840,000 |
| regressions caught (FAIL) | 3 | 3 (recall 1.00) |
| warnings caught (WARN) | 2 | 1 |
| check conclusion equals full-suite conclusion | – | 13/13 |

## Per scenario

| scenario | selected | full-suite FAIL | full-suite WARN | missed by targeting | wall s full → targeted |
| --- | --- | --- | --- | --- | --- |
| docs_only | 1/8 | – | – | none | 73 → 2 |
| prompt_wording | 7/8 | – | – | none | 72 → 71 |
| r1_dynamic_head | 7/8 | bench:chat_perf_gate, check:prompt_prefix_stable | – | none | 85 → 84 |
| r2_context_bloat | 5/8 | – | – | none | 74 → 67 |
| r3_citation_strip | 7/8 | – | – | none | 71 → 70 |
| r3b_chunk_regex_strip | 3/8 | – | – | none | 73 → 12 |
| r4_approval_removed | 1/8 | security:approval_gate | bench:chat_perf_gate | bench:chat_perf_gate (warn) | 72 → 2 |
| r5_prefix_caching_off | 3/8 | – | check:citation_required | none | 72 → 57 |
| max_tokens_up | 4/8 | – | – | none | 71 → 57 |
| model_swap | 4/8 | – | – | none | 72 → 57 |
| test_only | 2/8 | – | – | none | 72 → 3 |
| dependency_bump | 3/8 | – | – | none | 86 → 19 |
| health_payload | 1/8 | – | – | none | 72 → 2 |

## Seeded regressions the full suite did not catch (suite sensitivity, not selection)

- **r2_context_bloat** (R2 context bloat): no FAIL in the full suite; WARN: none. see per-item details in the scenario JSON.
- **r3_citation_strip** (R3 citations dropped): no FAIL in the full suite; WARN: none. see per-item details in the scenario JSON.
- **r3b_chunk_regex_strip** (R3b ineffective tag strip): no FAIL in the full suite; WARN: none. see per-item details in the scenario JSON.
- **r5_prefix_caching_off** (R5 prefix caching off (serving config)): no FAIL in the full suite; WARN: check:citation_required. serving config is not deployed per revision; every revision runs on the same endpoint.
