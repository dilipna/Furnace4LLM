# No regressions in 4 targeted checks

conclusion: success

**Ran 4 of 8 suite items** selected from the behavior-to-code graph. Change categories: generation_config.

### Quality

| check | result | detail |
|---|---|---|
| `check:citation_required` | **PASS** | citation contract met in 1/34 answers on the PR vs 0/34 on base (+2.9 pts; budget -5 pts; p=1.00); via full answer path (incl. post-processing) |
| `judge:ungrounded_answer` | **SKIP** | no judge model key configured (BYOK); judge not run |

### Performance

| check | result | detail |
|---|---|---|
| `bench:chat_perf_gate` | **PASS** | median p95 TTFT 238.4 -> 226.4 ms (-5.0%, pass; 3 runs each, runs overlap); prefix-cache hit 98% -> 98% |

### Security

| check | result | detail |
|---|---|---|
| `security:approval_gate` | **PASS** | 1 approval test(s) (generated from the base revision): 1 passed in 0.30s |

<details><summary>Not run for this change</summary>

- `unit:tests/test_retriever.py`: exercises nothing this change touches
- `unit:tests/test_prompts.py`: exercises nothing this change touches
- `check:prompt_prefix_stable`: exercises nothing this change touches
- `check:context_budget`: exercises nothing this change touches

</details>

### What changed in the graph

- `config_key:config/rag.yaml#generation.max_tokens`: `value` 256 -> 1024
