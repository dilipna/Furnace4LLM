# RQ2: evaluator quality

## 1. Seeded failures (deterministic checks)

Ground truth = the operator's effect on the check's specification. Sources: real F1 answers from two models (`bench/results/2026-10-04-f1-quality`), the 34 documented gold answers, and handwritten controls. This verifies detection of each failure class and the false-positive rate on clean controls; it is not agreement with human judgment.

| check | recall | precision | FPR | TP | FN | FP | TN |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| citation_required | 1.000 | 1.000 | 0.000 | 122 | 0 | 0 | 78 |
| duplicate_action | 1.000 | 1.000 | 0.000 | 2 | 0 | 0 | 2 |
| forbidden_pattern | 1.000 | 1.000 | 0.000 | 200 | 0 | 0 | 45 |
| prompt_prefix_stable | 1.000 | 1.000 | 0.000 | 80 | 0 | 0 | 80 |
| side_effect_requires_approval | 1.000 | 1.000 | 0.000 | 3 | 0 | 0 | 3 |

### Per operator

| check | operator | n | as expected |
| --- | --- | ---: | ---: |
| citation_required | blind_spot:cite_wrong_retrieved_doc | 31 | 31 |
| citation_required | cite_unretrieved | 44 | 44 |
| citation_required | control:documented_refusal | 34 | 34 |
| citation_required | control:gold_cited | 34 | 34 |
| citation_required | control:real_cited_answer | 10 | 10 |
| citation_required | strip_citations | 44 | 44 |
| citation_required | undocumented_refusal | 34 | 34 |
| duplicate_action | control:different_args | 1 | 1 |
| duplicate_action | control:retry_not_executed | 1 | 1 |
| duplicate_action | duplicate_reordered_args | 1 | 1 |
| duplicate_action | duplicate_same_args | 1 | 1 |
| forbidden_pattern | control:non_luhn_16_digits | 1 | 1 |
| forbidden_pattern | control:phone_number | 1 | 1 |
| forbidden_pattern | control:price_and_limits | 1 | 1 |
| forbidden_pattern | control:real_answer | 40 | 40 |
| forbidden_pattern | control:serial_and_version | 1 | 1 |
| forbidden_pattern | control:url | 1 | 1 |
| forbidden_pattern | inject_aws_key | 40 | 40 |
| forbidden_pattern | inject_card_luhn | 40 | 40 |
| forbidden_pattern | inject_card_luhn_nospace | 40 | 40 |
| forbidden_pattern | inject_email | 40 | 40 |
| forbidden_pattern | inject_github_token | 40 | 40 |
| prompt_prefix_stable | control:dynamic_suffix | 40 | 40 |
| prompt_prefix_stable | control:real_pair | 40 | 40 |
| prompt_prefix_stable | dynamic_early_middle | 40 | 40 |
| prompt_prefix_stable | dynamic_head | 40 | 40 |
| side_effect_requires_approval | control:approved | 1 | 1 |
| side_effect_requires_approval | control:blocked_not_executed | 1 | 1 |
| side_effect_requires_approval | control:read_only_action | 1 | 1 |
| side_effect_requires_approval | executed_approval_unknown | 1 | 1 |
| side_effect_requires_approval | executed_unapproved | 1 | 1 |
| side_effect_requires_approval | unapproved_after_read | 1 | 1 |

Known blind spot (by design, not counted above): an answer citing a *retrieved but wrong* document passes `citation_required` in 31/31 seeded cases. Catching it needs a semantic judge.

Gold questions whose gold document was not retrieved by F1's BM25 top-3 (excluded from gold items): 0/34.

## 2. Human-labeled items

**Pending.** Labeling queue `bench/labels/f1_queue.jsonl` (60 real answers, stratified by model and question kind). Label with `uv run python bench/label.py  (writes bench/labels/f1_labels.jsonl)`.

## 3. LLM judge

**Not run**: no judge key configured (BYOK Groq/OpenRouter). Judge TPR/TNR on held-out labels is pending.
