# No regressions in 3 targeted checks

conclusion: success

**Ran 3 of 8 suite items** selected from the behavior-to-code graph. Change categories: code, imports.

### Quality

| check | result | detail |
|---|---|---|
| `check:citation_required` | **PASS** | citation contract met in 0/34 answers on the PR vs 0/34 on base (-0.0 pts; budget -5 pts; p=1.00); via full answer path (incl. post-processing) |
| `judge:ungrounded_answer` | **SKIP** | no judge model key configured (BYOK); judge not run |

### Security

| check | result | detail |
|---|---|---|
| `security:approval_gate` | **PASS** | 1 approval test(s) (generated from the base revision): 1 passed in 0.31s |

<details><summary>Not run for this change</summary>

- `unit:tests/test_retriever.py`: exercises nothing this change touches
- `unit:tests/test_prompts.py`: exercises nothing this change touches
- `check:prompt_prefix_stable`: exercises nothing this change touches
- `check:context_budget`: exercises nothing this change touches
- `bench:chat_perf_gate`: exercises workflow:app/main.py::POST /chat, but the change (code, imports) is not one it detects

</details>

### What changed in the graph

