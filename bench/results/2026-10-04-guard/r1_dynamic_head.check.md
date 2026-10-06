# 2 regressions found: prompt_prefix_stable, chat_perf_gate

conclusion: failure

**Ran 7 of 8 suite items** selected from the behavior-to-code graph. Change categories: code, imports, prompt.

### Quality

| check | result | detail |
|---|---|---|
| `check:citation_required` | **PASS** | citation contract met in 6/34 answers on the PR vs 5/34 on base (+2.9 pts; budget -5 pts); via full answer path (incl. post-processing) |
| `judge:ungrounded_answer` | **SKIP** | no judge model key configured (BYOK); judge not run |

### Performance

| check | result | detail |
|---|---|---|
| `check:prompt_prefix_stable` | **FAIL** | requests share 15 leading characters (base 3954, need 3558) |
| `check:context_budget` | **PASS** | largest prompt 1024 tokens (base 980) against a budget of 3840; median 1007 vs 964 |
| `bench:chat_perf_gate` | **FAIL** | median p95 TTFT 624.1 -> 1500.2 ms (+140.4%, block; 3 runs each, runs separated); prefix-cache hit 85% -> 0% |

### Security

| check | result | detail |
|---|---|---|
| `security:approval_gate` | **PASS** | 1 approval test(s) (generated from the base revision): 1 passed in 0.23s |

### Tests

| check | result | detail |
|---|---|---|
| `unit:tests/test_prompts.py` | **PASS** | 2 passed in 0.34s |

<details><summary>Not run for this change</summary>

- `unit:tests/test_retriever.py`: exercises nothing this change touches

</details>

### What changed in the graph

- `prompt:app/prompts.py::build_messages#system`: `static_prefix_chars` 3927 -> 8; `static_chars` 3927 -> 3940; `dynamic_head` False -> True
