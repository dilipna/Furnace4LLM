# No regressions in 2 targeted checks

conclusion: success

**Ran 2 of 8 suite items** selected from the behavior-to-code graph. Change categories: tests.

### Security

| check | result | detail |
|---|---|---|
| `security:approval_gate` | **PASS** | 1 approval test(s) (generated from the base revision): 1 passed in 0.37s |

### Tests

| check | result | detail |
|---|---|---|
| `unit:tests/test_retriever.py` | **PASS** | 3 passed in 0.54s |

<details><summary>Not run for this change</summary>

- `unit:tests/test_prompts.py`: exercises nothing this change touches
- `check:citation_required`: exercises nothing this change touches
- `judge:ungrounded_answer`: exercises nothing this change touches
- `check:prompt_prefix_stable`: exercises nothing this change touches
- `check:context_budget`: exercises nothing this change touches
- `bench:chat_perf_gate`: exercises nothing this change touches

</details>

### What changed in the graph

