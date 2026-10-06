# 1 regression found: approval_gate

conclusion: failure

**Ran 1 of 8 suite items** selected from the behavior-to-code graph. Change categories: code, tool.

### Security

| check | result | detail |
|---|---|---|
| `security:approval_gate` | **FAIL** | 1 approval test(s) (generated from the base revision): 1 failed in 0.20s | >       assert not isinstance(exc.value, _NoOutbound), "side effect executed without approval" |

<details><summary>Not run for this change</summary>

- `unit:tests/test_retriever.py`: exercises nothing this change touches
- `unit:tests/test_prompts.py`: exercises nothing this change touches
- `check:citation_required`: exercises nothing this change touches
- `judge:ungrounded_answer`: exercises nothing this change touches
- `check:prompt_prefix_stable`: exercises nothing this change touches
- `check:context_budget`: exercises nothing this change touches
- `bench:chat_perf_gate`: exercises nothing this change touches

</details>

### What changed in the graph

- `security_boundary:app/tickets.py::create_ticket#approval`: `exists` True -> False
- `tool:app/tickets.py::create_ticket`: `approval_gate` True -> False
