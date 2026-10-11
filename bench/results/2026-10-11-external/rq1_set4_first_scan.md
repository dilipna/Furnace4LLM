# RQ1: reconstruction accuracy

Deterministic reconstruction only (LLM synthesis is not built, so no +LLM ablation). F1 is the development fixture; held-out apps were labeled from source before their first scan (labels: `bench/ground_truth/`, written by the developer agent, not yet independently reviewed).

## Micro-averaged P / R / F1

| category | F1 (dev) | held-out set 1 | held-out set 2 | held-out set 3 | held-out set 4 |
| --- | --- | --- | --- | --- | --- |
| routes | – | – | – | – | 1.00 / 0.77 / 0.87 (10/10p/13t) |
| llm_call_sites | – | – | – | – | 1.00 / 0.22 / 0.36 (2/2p/9t) |
| models | – | – | – | – | – / 0.00 / 0.00 (0/0p/6t) |
| serving_engines | – | – | – | – | 1.00 / 0.67 / 0.80 (2/2p/3t) |
| retrievers | – | – | – | – | – / 0.00 / 0.00 (0/0p/2t) |
| tools | – | – | – | – | – / 0.00 / 0.00 (0/0p/2t) |
| prompts | – | – | – | – | 0.12 / 0.40 / 0.19 (2/16p/5t) |
| workflows | – | – | – | – | 0.00 / 0.00 / 0.00 (0/1p/7t) |
| contradictions | – | – | – | – | 0.00 / 0.00 / 0.00 (0/4p/1t) |

Attribute accuracy (held-out-4): 25/26 (a scan that finds nothing scores 15/21 on the same truth)

## Per app

### openai-chat-backend-fastapi (held-out-4, scan 0.1s)

| category | P / R / F1 (tp/pred/truth) | missed | false positives |
| --- | --- | --- | --- |
| routes | 1.00 / 1.00 / 1.00 (2/2p/2t) | – | – |
| llm_call_sites | – / 0.00 / 0.00 (0/0p/2t) | src/api/chat.py::chat_handler; src/api/chat.py::response_stream | – |
| models | – / 0.00 / 0.00 (0/0p/1t) | gpt-5.2 | – |
| serving_engines | – / 0.00 / 0.00 (0/0p/1t) | openai | – |
| retrievers | n/a | – | – |
| tools | n/a | – | – |
| prompts | 0.00 / 0.00 / 0.00 (0/2p/1t) | src/api/chat.py::SYSTEM_PROMPT | src/api/chat.py::chat_handler#system; src/api/chat.py::chat_stream_handler#system |
| workflows | – / 0.00 / 0.00 (0/0p/2t) | POST /chat; POST /chat/stream | – |
| contradictions | n/a | – | – |

Attributes correct: 7/7

### rag-postgres-openai-python (held-out-4, scan 0.9s)

| category | P / R / F1 (tp/pred/truth) | missed | false positives |
| --- | --- | --- | --- |
| routes | 1.00 / 0.71 / 0.83 (5/5p/7t) | GET /; GET /favicon.ico | – |
| llm_call_sites | 1.00 / 0.17 / 0.29 (1/1p/6t) | src/backend/fastapi_app/rag_simple.py::SimpleRAGChat.answer; src/backend/fastapi_app/rag_simple.py::SimpleRAGChat.answer_stream; src/backend/fastapi_app/rag_advanced.py::AdvancedRAGChat.prepare_context; src/backend/fastapi_app/rag_advanced.py::AdvancedRAGChat.answer; src/backend/fastapi_app/rag_advanced.py::AdvancedRAGChat.answer_stream | – |
| models | – / 0.00 / 0.00 (0/0p/4t) | gpt-5.4; gpt-3.5-turbo; phi3:3.8b; llama3.1 | – |
| serving_engines | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| retrievers | – / 0.00 / 0.00 (0/0p/1t) | src/backend/fastapi_app/postgres_searcher.py::PostgresSearcher.search | – |
| tools | – / 0.00 / 0.00 (0/0p/1t) | search_database | – |
| prompts | 0.00 / 0.00 / 0.00 (0/8p/2t) | src/backend/fastapi_app/rag_base.py::RAGChatBase.answer_prompt_template; src/backend/fastapi_app/rag_advanced.py::AdvancedRAGChat.query_prompt_template | src/backend/fastapi_app/prompts/answer.txt; src/backend/fastapi_app/prompts/query.txt; evals/generate_ground_truth.py::generate_ground_truth_data#system; src/backend/fastapi_app/rag_advanced.py::AdvancedRAGChat.prepare_context#system; src/backend/fastapi_app/rag_advanced.py::AdvancedRAGChat.answer#system; src/backend/fastapi_app/rag_advanced.py::AdvancedRAGChat.answer_stream#system; src/backend/fastapi_app/rag_simple.py::SimpleRAGChat.answer#system; src/backend/fastapi_app/rag_simple.py::SimpleRAGChat.answer_stream#system |
| workflows | 0.00 / 0.00 / 0.00 (0/1p/2t) | POST /chat; POST /chat/stream | workflow:evals/generate_ground_truth.py::cli:evals/generate_ground_truth.py |
| contradictions | 0.00 / – / 0.00 (0/4p/0t) | – | serving_engine: ['openai', 'ollama']; serving_engine: ['openai', 'ollama']; serving_engine: ['openai', 'ollama']; model: ['gpt-4o-mini', 'llama3.1'] |

Attributes correct: 9/9

### tech-trends-chatbot (held-out-4, scan 0.3s)

| category | P / R / F1 (tp/pred/truth) | missed | false positives |
| --- | --- | --- | --- |
| routes | 1.00 / 0.75 / 0.86 (3/3p/4t) | HEAD /health | – |
| llm_call_sites | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| models | – / 0.00 / 0.00 (0/0p/1t) | gpt-4.1-mini | – |
| serving_engines | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| retrievers | – / 0.00 / 0.00 (0/0p/1t) | backend/app/db.py::search_vector_db | – |
| tools | – / 0.00 / 0.00 (0/0p/1t) | QueryKnowledgeBaseTool | – |
| prompts | 0.33 / 1.00 / 0.50 (2/6p/2t) | – | backend/app/assistants/assistant.py::RAGAssistant.__init__#system; backend/app/assistants/assistant.py::RAGAssistant.__init__#system; backend/app/assistants/local_assistant.py::LocalRAGAssistant.__init__#system; backend/app/assistants/local_assistant.py::LocalRAGAssistant.__init__#system |
| workflows | – / 0.00 / 0.00 (0/0p/3t) | POST /chats/{chat_id}; script:backend/app/assistants/local_assistant.py; script:backend/app/loader.py | – |
| contradictions | – / 0.00 / 0.00 (0/0p/1t) | model: ['GPT-4o', 'gpt-4.1-mini'] | – |

Attributes correct: 9/10; wrong: `call.model` truth='gpt-4.1-mini' pred=None

## Confidence calibration (all apps)

ECE = 0.171 over n = 9 decidable claims.

| confidence bin | n | mean confidence | accuracy |
| --- | ---: | ---: | ---: |
| [0.6, 0.8) | 4 | 0.68 | 1.00 |
| [0.8, 1.0) | 5 | 0.94 | 1.00 |
