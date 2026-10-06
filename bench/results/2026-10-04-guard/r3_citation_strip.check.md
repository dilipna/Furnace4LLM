# 1 regression found: citation_required

conclusion: failure

**Ran 7 of 8 suite items** selected from the behavior-to-code graph. Change categories: prompt.

### Quality

| check | result | detail |
|---|---|---|
| `check:citation_required` | **FAIL** | citation contract met in 2/34 answers on the PR vs 5/34 on base (-8.8 pts; budget -5 pts); via full answer path (incl. post-processing) |
| `judge:ungrounded_answer` | **SKIP** | no judge model key configured (BYOK); judge not run |

### Performance

| check | result | detail |
|---|---|---|
| `check:prompt_prefix_stable` | **PASS** | requests share 3875 leading characters (base 3954, need 3558) |
| `check:context_budget` | **PASS** | largest prompt 959 tokens (base 980) against a budget of 3840; median 943 vs 964 |
| `bench:chat_perf_gate` | **PASS** | median p95 TTFT 204.5 -> 211.1 ms (+3.2%, pass; 3 runs each, runs overlap); prefix-cache hit 98% -> 98% |

### Security

| check | result | detail |
|---|---|---|
| `security:approval_gate` | **PASS** | 1 approval test(s) (generated from the base revision): 1 passed in 0.20s |

### Tests

| check | result | detail |
|---|---|---|
| `unit:tests/test_prompts.py` | **PASS** | 2 passed in 0.46s |

<details><summary>Not run for this change</summary>

- `unit:tests/test_retriever.py`: exercises nothing this change touches

</details>

### What changed in the graph

- `prompt:app/prompts.py::SYSTEM_PROMPT`: `static_chars` 3927 -> 3848; `approx_tokens` 982 -> 962
- `prompt:app/prompts.py::build_messages#system`: `static_prefix_chars` 3927 -> 3848; `static_chars` 3927 -> 3848
