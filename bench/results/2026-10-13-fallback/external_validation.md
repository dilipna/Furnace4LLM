# External validation (held-out set 4): Scan, Forge, Guard, repair

Apps labeled and committed before this script first ran; Guard scenarios are synthetic edits applied to the real source; expected selections are the correct behavior, fixed before the run. RQ1 scores call sites, models and routes on the same apps (rq1.md).

## Scan: findings link to real source

| app | py files | scan s | findings | evidence checked | of which file-existence only | broken links |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| openai-chat-backend-fastapi | 7 | 0.58 | 4 | 5 | 1 | 0 |
| rag-postgres-openai-python | 34 | 2.83 | 4 | 10 | 0 | 0 |
| tech-trends-chatbot | 16 | 0.91 | 7 | 5 | 0 | 0 |

## Forge

| app | planned | files | skipped | sandbox validation |
| --- | ---: | ---: | ---: | ---: |
| openai-chat-backend-fastapi | True | 0 | 2 | not run (--sandbox) |
| rag-postgres-openai-python | True | 0 | 4 | not run (--sandbox) |
| tech-trends-chatbot | True | 7 | 1 | not run (--sandbox) |

## Guard impact on synthetic PRs (generic suite)

| app | scenario | categories | selected | signature | correct | why not |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| openai-chat-backend-fastapi | prompt_dynamic_head | code, imports, prompt | bench:perf_gate, check:answer_quality, check:prompt_prefix_stable, unit:existing_tests | prefix_instability | yes |  |
| openai-chat-backend-fastapi | docs_only | docs | none | – | yes |  |
| openai-chat-backend-fastapi | code_unrelated | code_off_llm_path | none | – | yes |  |
| rag-postgres-openai-python | prompt_dynamic_head | code, imports, prompt | bench:perf_gate, check:prompt_prefix_stable, unit:existing_tests | prefix_instability | yes |  |
| rag-postgres-openai-python | docs_only | docs | none | – | yes |  |
| rag-postgres-openai-python | code_unrelated | code_off_llm_path | none | – | yes |  |
| tech-trends-chatbot | prompt_dynamic_head | code, prompt | bench:perf_gate, check:prompt_prefix_stable, unit:existing_tests | prefix_instability | yes |  |
| tech-trends-chatbot | docs_only | docs | none | – | yes |  |
| tech-trends-chatbot | code_unrelated | code_off_llm_path | none | – | yes |  |

## Repair applicability (prompt scenario)

- openai-chat-backend-fastapi (prompt:src/api/chat.py::chat_handler#system): move_dynamic_to_suffix: prefix-stable after edit; move_dynamic_to_log: prefix-stable after edit
- rag-postgres-openai-python (prompt:src/backend/fastapi_app/rag_simple.py::SimpleRAGChat.__init__@Answerer#system): move_dynamic_to_suffix: not applicable (function SimpleRAGChat.__init__@Answerer not found); move_dynamic_to_log: not applicable (function SimpleRAGChat.__init__@Answerer not found)
- tech-trends-chatbot (prompt:backend/app/assistants/assistant.py::RAGAssistant.__init__#system): move_dynamic_to_suffix: not applicable (no system message in RAGAssistant.__init__); move_dynamic_to_log: not applicable (no system message in RAGAssistant.__init__)
