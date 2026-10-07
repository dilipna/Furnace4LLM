# No regressions in 7 targeted checks

conclusion: success

**Ran 7 of 8 suite items** selected from the behavior-to-code graph. Change categories: prompt.

### Quality

| check | result | detail |
|---|---|---|
| `check:citation_required` | **PASS** | citation contract met in 1/34 answers on the PR vs 0/34 on base (+2.9 pts; budget -5 pts; p=1.00); via full answer path (incl. post-processing) |
| `judge:ungrounded_answer` | **SKIP** | no judge model key configured (BYOK); judge not run |

### Performance

| check | result | detail |
|---|---|---|
| `check:prompt_prefix_stable` | **PASS** | requests share 3964 leading characters (base 3954, need 3558) |
| `check:context_budget` | **PASS** | largest prompt 982 tokens (base 980) against a budget of 3840; median 966 vs 964 |
| `bench:chat_perf_gate` | **PASS** | median p95 TTFT 228.4 -> 231.8 ms (+1.5%, pass; 3 runs each, runs overlap); prefix-cache hit 98% -> 98% |

### Security

| check | result | detail |
|---|---|---|
| `security:approval_gate` | **PASS** | 1 approval test(s) (generated from the base revision): 1 passed in 0.27s |

### Tests

| check | result | detail |
|---|---|---|
| `unit:tests/test_prompts.py` | **PASS** | 2 passed in 0.49s |

<details><summary>Not run for this change</summary>

- `unit:tests/test_retriever.py`: exercises nothing this change touches

</details>

### What changed in the graph

- `prompt:app/prompts.py::SYSTEM_PROMPT`: `static_chars` 3927 -> 3937; `approx_tokens` 982 -> 984
- `prompt:app/prompts.py::build_messages#system`: `static_chars` 3927 -> 3937; `static_prefix_chars` 3927 -> 3937
