# No regressions in 3 targeted checks

conclusion: success

**Ran 3 of 8 suite items** selected from the behavior-to-code graph. Change categories: dependency.

### Security

| check | result | detail |
|---|---|---|
| `security:approval_gate` | **PASS** | 1 approval test(s) (generated from the base revision): 1 passed in 0.43s |

### Tests

| check | result | detail |
|---|---|---|
| `unit:tests/test_retriever.py` | **PASS** | 2 passed in 0.56s |
| `unit:tests/test_prompts.py` | **PASS** | 2 passed in 0.56s |

<details><summary>Not run for this change</summary>

- `check:citation_required`: exercises nothing this change touches
- `judge:ungrounded_answer`: exercises nothing this change touches
- `check:prompt_prefix_stable`: exercises nothing this change touches
- `check:context_budget`: exercises nothing this change touches
- `bench:chat_perf_gate`: exercises nothing this change touches

</details>

### What changed in the graph

