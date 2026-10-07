# No regressions in 3 targeted checks

conclusion: neutral

**Ran 3 of 8 suite items** selected from the behavior-to-code graph. Change categories: serving_config.

### Quality

| check | result | detail |
|---|---|---|
| `check:citation_required` | **WARN** | citation contract met in 0/34 answers on the PR vs 2/34 on base (-5.9 pts; budget -5 pts; not significant at n=34, one-sided Fisher p=0.25); via full answer path (incl. post-processing) |

### Performance

| check | result | detail |
|---|---|---|
| `bench:chat_perf_gate` | **PASS** | median p95 TTFT 234.5 -> 195.9 ms (-16.4%, pass; 3 runs each, runs overlap); prefix-cache hit 98% -> 98% |

### Security

| check | result | detail |
|---|---|---|
| `security:approval_gate` | **PASS** | 1 approval test(s) (generated from the base revision): 1 passed in 0.31s |

<details><summary>Not run for this change</summary>

- `unit:tests/test_retriever.py`: exercises nothing this change touches
- `unit:tests/test_prompts.py`: exercises nothing this change touches
- `judge:ungrounded_answer`: exercises capability:route:app/main.py::POST /chat::rag_answer, but the change (serving_config) is not one it detects
- `check:prompt_prefix_stable`: exercises nothing this change touches
- `check:context_budget`: exercises nothing this change touches

</details>

### What changed in the graph

- `config_key:docker-compose.yml#llm.--enable-prefix-caching`: `exists` True -> False
- `config_key:docker-compose.yml#llm.--no-enable-prefix-caching`: `exists` False -> True
- `serving_config:docker-compose.yml::llm`: `flags` {'served-model-name': 'lab', 'gpu-memory-utilization': '0.70', 'max-model-len': '4096', 'max-num-seqs': '32', 'enable-prefix-caching': True} -> {'served-model-name': 'lab', 'gpu-memory-utilization': '0.70', 'max-model-len': '4096', 'max-num-seqs': '32', 'no-enable-prefix-caching': True}
