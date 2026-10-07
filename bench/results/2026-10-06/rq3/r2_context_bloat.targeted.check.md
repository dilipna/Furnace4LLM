# No regressions in 5 targeted checks

conclusion: success

**Ran 5 of 8 suite items** selected from the behavior-to-code graph. Change categories: retrieval, retrieval_config.

### Quality

| check | result | detail |
|---|---|---|
| `check:citation_required` | **PASS** | citation contract met in 1/34 answers on the PR vs 0/34 on base (+2.9 pts; budget -5 pts; p=1.00); via full answer path (incl. post-processing) |
| `judge:ungrounded_answer` | **SKIP** | no judge model key configured (BYOK); judge not run |

### Performance

| check | result | detail |
|---|---|---|
| `check:context_budget` | **PASS** | largest prompt 1264 tokens (base 980) against a budget of 3840; median 1228 vs 964 |
| `bench:chat_perf_gate` | **PASS** | median p95 TTFT 234.2 -> 215.3 ms (-8.1%, pass; 3 runs each, runs overlap); prefix-cache hit 98% -> 98% |

### Security

| check | result | detail |
|---|---|---|
| `security:approval_gate` | **PASS** | 1 approval test(s) (generated from the base revision): 1 passed in 0.38s |

<details><summary>Not run for this change</summary>

- `unit:tests/test_retriever.py`: exercises component:app/retriever.py::retrieve, but the change (retrieval, retrieval_config) is not one it detects
- `unit:tests/test_prompts.py`: exercises nothing this change touches
- `check:prompt_prefix_stable`: exercises nothing this change touches

</details>

### What changed in the graph

- `config_key:config/rag.yaml#retrieval.max_context_chars`: `value` 6000 -> 24000
- `config_key:config/rag.yaml#retrieval.top_k`: `value` 3 -> 12
- `retriever:app/retriever.py::retrieve`: `top_k` 3 -> 12
