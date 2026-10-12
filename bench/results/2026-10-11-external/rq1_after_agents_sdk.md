# RQ1: reconstruction accuracy

Deterministic reconstruction only (LLM synthesis is not built, so no +LLM ablation). F1 is the development fixture; held-out apps were labeled from source before their first scan (labels: `bench/ground_truth/`, written by the developer agent, not yet independently reviewed).

## Micro-averaged P / R / F1

| category | F1 (dev) | held-out set 1 | held-out set 2 | held-out set 3 | held-out set 4 | held-out set 5 |
| --- | --- | --- | --- | --- | --- | --- |
| routes | 1.00 / 1.00 / 1.00 (3/3p/3t) | n/a | 1.00 / 1.00 / 1.00 (2/2p/2t) | n/a | 1.00 / 0.77 / 0.87 (10/10p/13t) | 1.00 / 1.00 / 1.00 (5/5p/5t) |
| llm_call_sites | 1.00 / 1.00 / 1.00 (1/1p/1t) | 1.00 / 1.00 / 1.00 (8/8p/8t) | 1.00 / 1.00 / 1.00 (5/5p/5t) | 1.00 / 0.89 / 0.94 (8/8p/9t) | 1.00 / 1.00 / 1.00 (9/9p/9t) | 1.00 / 1.00 / 1.00 (3/3p/3t) |
| models | 1.00 / 1.00 / 1.00 (1/1p/1t) | 1.00 / 1.00 / 1.00 (4/4p/4t) | 1.00 / 1.00 / 1.00 (2/2p/2t) | 1.00 / 0.18 / 0.30 (3/3p/17t) | – / 0.00 / 0.00 (0/0p/6t) | 1.00 / 0.50 / 0.67 (1/1p/2t) |
| serving_engines | 1.00 / 1.00 / 1.00 (1/1p/1t) | 1.00 / 1.00 / 1.00 (4/4p/4t) | 1.00 / 0.67 / 0.80 (2/2p/3t) | 1.00 / 0.80 / 0.89 (4/4p/5t) | 1.00 / 0.67 / 0.80 (2/2p/3t) | – / 0.00 / 0.00 (0/0p/1t) |
| retrievers | 1.00 / 1.00 / 1.00 (1/1p/1t) | 1.00 / 1.00 / 1.00 (2/2p/2t) | n/a | 0.67 / 1.00 / 0.80 (2/3p/2t) | – / 0.00 / 0.00 (0/0p/2t) | n/a |
| tools | 1.00 / 1.00 / 1.00 (1/1p/1t) | – / 0.00 / 0.00 (0/0p/1t) | n/a | n/a | – / 0.00 / 0.00 (0/0p/2t) | – / 0.00 / 0.00 (0/0p/11t) |
| prompts | 1.00 / 1.00 / 1.00 (1/1p/1t) | 1.00 / 0.33 / 0.50 (1/1p/3t) | 0.00 / 0.00 / 0.00 (0/3p/4t) | 0.00 / 0.00 / 0.00 (0/2p/2t) | 0.12 / 0.40 / 0.19 (2/16p/5t) | – / 0.00 / 0.00 (0/0p/8t) |
| workflows | 1.00 / 1.00 / 1.00 (2/2p/2t) | 1.00 / 0.67 / 0.80 (6/6p/9t) | 1.00 / 0.80 / 0.89 (4/4p/5t) | 1.00 / 0.67 / 0.80 (6/6p/9t) | 0.67 / 0.29 / 0.40 (2/3p/7t) | – / 0.00 / 0.00 (0/0p/1t) |
| contradictions | 1.00 / 1.00 / 1.00 (1/1p/1t) | – / 0.00 / 0.00 (0/0p/1t) | 1.00 / 1.00 / 1.00 (1/1p/1t) | 0.00 / 0.00 / 0.00 (0/3p/2t) | 0.00 / 0.00 / 0.00 (0/4p/1t) | n/a |

Attribute accuracy (dev): 13/13 (a scan that finds nothing scores 4/7 on the same truth)

Attribute accuracy (held-out): 46/46 (a scan that finds nothing scores 15/20 on the same truth)

Attribute accuracy (held-out-2): 27/28 (a scan that finds nothing scores 13/14 on the same truth)

Attribute accuracy (held-out-3): 62/63 (a scan that finds nothing scores 32/35 on the same truth)

Attribute accuracy (held-out-4): 41/42 (a scan that finds nothing scores 15/21 on the same truth)

Attribute accuracy (held-out-5): 15/16 (a scan that finds nothing scores 7/7 on the same truth)

## Per app

### support-rag-py (F1) (dev, scan 0.6s)

| category | P / R / F1 (tp/pred/truth) | missed | false positives |
| --- | --- | --- | --- |
| routes | 1.00 / 1.00 / 1.00 (3/3p/3t) | – | – |
| llm_call_sites | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| models | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| serving_engines | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| retrievers | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| tools | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| prompts | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| workflows | 1.00 / 1.00 / 1.00 (2/2p/2t) | – | – |
| contradictions | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |

Attributes correct: 13/13

Prompt slot duplicates (not scored): app/prompts.py::build_messages#system

### ask-multiple-pdfs (held-out, scan 0.1s)

| category | P / R / F1 (tp/pred/truth) | missed | false positives |
| --- | --- | --- | --- |
| routes | n/a | – | – |
| llm_call_sites | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| models | n/a | – | – |
| serving_engines | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| retrievers | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| tools | n/a | – | – |
| prompts | n/a | – | – |
| workflows | – / 0.00 / 0.00 (0/0p/1t) | streamlit:app.py | – |
| contradictions | – / 0.00 / 0.00 (0/0p/1t) | entrypoint: ['app.py', 'main.py'] | – |

Attributes correct: 10/10

### Bedrock-ChatBot-with-LangChain-and-Streamlit (held-out-3, scan 0.4s)

| category | P / R / F1 (tp/pred/truth) | missed | false positives |
| --- | --- | --- | --- |
| routes | n/a | – | – |
| llm_call_sites | 1.00 / 0.75 / 0.86 (3/3p/4t) | bedrock/models.py::ChatModel.__init__ | – |
| models | 1.00 / 0.10 / 0.18 (1/1p/10t) | anthropic.claude-3-sonnet-20240229-v1:0; anthropic.claude-3-haiku-20240307-v1:0; mistral.mistral-large-2402-v1:0; us.deepseek.r1-v1:0; us.anthropic.claude-3-7-sonnet-20250219-v1:0; anthropic.claude-3-5-haiku-20241022-v1:0; us.amazon.nova-pro-v1:0; us.amazon.nova-lite-v1:0; us.amazon.nova-micro-v1:0 | – |
| serving_engines | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| retrievers | 0.50 / 1.00 / 0.67 (1/2p/1t) | – | retriever:bedrock/bedrock_embedder.py::rag_search |
| tools | n/a | – | – |
| prompts | 0.00 / 0.00 / 0.00 (0/2p/1t) | bedrock/role_prompt.py | simple/bedrock_chatbot.py::DEFAULT_CLAUDE_TEMPLATE; streaming/bedrock_simple.py::DEFAULT_CLAUDE_TEMPLATE |
| workflows | 1.00 / 0.60 / 0.75 (3/3p/5t) | streamlit:bedrock/bedrock_chatbot.py; cli:bedrock_indexer.py | – |
| contradictions | 0.00 / 0.00 / 0.00 (0/1p/1t) | entrypoint: ['bedrock/bedrock_chatbot.py', 'bedrock_chatbot_claude_3_sonnet_vision.py', 'bedrock_chatbot_claude_3_sonnet.py'] | model: ['anthropic.claude-v2', 'Claude 3', 'DeepSeek', 'claude-3-langchain-streamlit', 'Claude itself'] |

Attributes correct: 18/18

### gemini_multipdf_chat (held-out-3, scan 0.2s)

| category | P / R / F1 (tp/pred/truth) | missed | false positives |
| --- | --- | --- | --- |
| routes | n/a | – | – |
| llm_call_sites | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| models | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| serving_engines | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| retrievers | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| tools | n/a | – | – |
| prompts | – / 0.00 / 0.00 (0/0p/1t) | app.py::get_conversational_chain | – |
| workflows | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| contradictions | 0.00 / 0.00 / 0.00 (0/1p/1t) | entrypoint: ['app.py', 'main.py'] | model: ['Gemini', 'gemini-pro', 'gemini_multipdf_chat', 'gemini_multipdf_chat.git', 'gemini-pdf-chatbot.git'] |

Attributes correct: 12/12

### llama2 (held-out-2, scan 0.2s)

| category | P / R / F1 (tp/pred/truth) | missed | false positives |
| --- | --- | --- | --- |
| routes | n/a | – | – |
| llm_call_sites | 1.00 / 1.00 / 1.00 (4/4p/4t) | – | – |
| models | 1.00 / 1.00 / 1.00 (2/2p/2t) | – | – |
| serving_engines | 1.00 / 1.00 / 1.00 (2/2p/2t) | – | – |
| retrievers | n/a | – | – |
| tools | n/a | – | – |
| prompts | – / 0.00 / 0.00 (0/0p/3t) | streamlit_app.py::string_dialogue; streamlit_app_v2.py::string_dialogue; app_v1.py::string_dialogue | – |
| workflows | 1.00 / 0.75 / 0.86 (3/3p/4t) | cli:llama2-local.py | – |
| contradictions | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |

Attributes correct: 19/19

### llamav2-chat (held-out-3, scan 0.1s)

| category | P / R / F1 (tp/pred/truth) | missed | false positives |
| --- | --- | --- | --- |
| routes | n/a | – | – |
| llm_call_sites | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| models | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| serving_engines | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| retrievers | n/a | – | – |
| tools | n/a | – | – |
| prompts | n/a | – | – |
| workflows | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| contradictions | n/a | – | – |

Attributes correct: 10/10

### llm-examples (held-out, scan 0.2s)

| category | P / R / F1 (tp/pred/truth) | missed | false positives |
| --- | --- | --- | --- |
| routes | n/a | – | – |
| llm_call_sites | 1.00 / 1.00 / 1.00 (6/6p/6t) | – | – |
| models | 1.00 / 1.00 / 1.00 (3/3p/3t) | – | – |
| serving_engines | 1.00 / 1.00 / 1.00 (2/2p/2t) | – | – |
| retrievers | n/a | – | – |
| tools | – / 0.00 / 0.00 (0/0p/1t) | Search | – |
| prompts | – / 0.00 / 0.00 (0/0p/2t) | pages/1_File_Q&A.py::prompt; pages/4_Langchain_PromptTemplate.py::template | – |
| workflows | 1.00 / 1.00 / 1.00 (6/6p/6t) | – | – |
| contradictions | n/a | – | – |

Attributes correct: 25/25

### mistral-streamlit-chat (held-out-3, scan 0.0s)

| category | P / R / F1 (tp/pred/truth) | missed | false positives |
| --- | --- | --- | --- |
| routes | n/a | – | – |
| llm_call_sites | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| models | – / 0.00 / 0.00 (0/0p/3t) | mistral-tiny; mistral-small; mistral-medium | – |
| serving_engines | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| retrievers | n/a | – | – |
| tools | n/a | – | – |
| prompts | n/a | – | – |
| workflows | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| contradictions | 0.00 / – / 0.00 (0/1p/0t) | – | model: ['Mistral', 'mistral-streamlit-chat.git', 'mistral-streamlit-chat', 'MISTRAL_API_KEY', 'mistral_chat.py'] |

Attributes correct: 10/10

### openai-chat-app-quickstart (held-out-2, scan 0.7s)

| category | P / R / F1 (tp/pred/truth) | missed | false positives |
| --- | --- | --- | --- |
| routes | 1.00 / 1.00 / 1.00 (2/2p/2t) | – | – |
| llm_call_sites | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| models | n/a | – | – |
| serving_engines | – / 0.00 / 0.00 (0/0p/1t) | openai | – |
| retrievers | n/a | – | – |
| tools | n/a | – | – |
| prompts | 0.00 / 0.00 / 0.00 (0/3p/1t) | src/quartapp/templates/index.html::system | tests/conftest.py::mock_openai_responses_stream.mock_stream#system; tests/test_app.py::test_chat_stream_text#system; tests/test_app.py::test_chat_stream_text_history#system |
| workflows | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| contradictions | n/a | – | – |

Attributes correct: 8/9; wrong: `rag.present` truth=False pred=True

### openai-chat-backend-fastapi (held-out-4, scan 0.1s)

| category | P / R / F1 (tp/pred/truth) | missed | false positives |
| --- | --- | --- | --- |
| routes | 1.00 / 1.00 / 1.00 (2/2p/2t) | – | – |
| llm_call_sites | 1.00 / 1.00 / 1.00 (2/2p/2t) | – | – |
| models | – / 0.00 / 0.00 (0/0p/1t) | gpt-5.2 | – |
| serving_engines | – / 0.00 / 0.00 (0/0p/1t) | openai | – |
| retrievers | n/a | – | – |
| tools | n/a | – | – |
| prompts | 0.00 / 0.00 / 0.00 (0/2p/1t) | src/api/chat.py::SYSTEM_PROMPT | src/api/chat.py::chat_handler#system; src/api/chat.py::chat_stream_handler#system |
| workflows | 1.00 / 1.00 / 1.00 (2/2p/2t) | – | – |
| contradictions | n/a | – | – |

Attributes correct: 13/13

### openai-cs-agents-demo (held-out-5, scan 0.3s)

| category | P / R / F1 (tp/pred/truth) | missed | false positives |
| --- | --- | --- | --- |
| routes | 1.00 / 1.00 / 1.00 (5/5p/5t) | – | – |
| llm_call_sites | 1.00 / 1.00 / 1.00 (3/3p/3t) | – | – |
| models | 1.00 / 0.50 / 0.67 (1/1p/2t) | gpt-5.2 | – |
| serving_engines | – / 0.00 / 0.00 (0/0p/1t) | openai | – |
| retrievers | n/a | – | – |
| tools | – / 0.00 / 0.00 (0/0p/11t) | faq_lookup_tool; get_trip_details; update_seat; flight_status_tool; baggage_tool; get_matching_flights; book_new_flight; assign_special_service_seat; issue_compensation; display_seat_map; cancel_flight | – |
| prompts | – / 0.00 / 0.00 (0/0p/8t) | python-backend/airline/agents.py::seat_services_instructions; python-backend/airline/agents.py::flight_information_instructions; python-backend/airline/agents.py::booking_cancellation_instructions; python-backend/airline/agents.py::refunds_compensation_instructions; python-backend/airline/agents.py::faq_agent; python-backend/airline/agents.py::triage_agent; python-backend/airline/guardrails.py::guardrail_agent; python-backend/airline/guardrails.py::jailbreak_guardrail_agent | – |
| workflows | – / 0.00 / 0.00 (0/0p/1t) | POST /chatkit | – |
| contradictions | n/a | – | – |

Attributes correct: 15/16; wrong: `call.model` truth='gpt-5.2' pred=None

### rag-postgres-openai-python (held-out-4, scan 0.7s)

| category | P / R / F1 (tp/pred/truth) | missed | false positives |
| --- | --- | --- | --- |
| routes | 1.00 / 0.71 / 0.83 (5/5p/7t) | GET /; GET /favicon.ico | – |
| llm_call_sites | 1.00 / 1.00 / 1.00 (6/6p/6t) | – | – |
| models | – / 0.00 / 0.00 (0/0p/4t) | gpt-5.4; gpt-3.5-turbo; phi3:3.8b; llama3.1 | – |
| serving_engines | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| retrievers | – / 0.00 / 0.00 (0/0p/1t) | src/backend/fastapi_app/postgres_searcher.py::PostgresSearcher.search | – |
| tools | – / 0.00 / 0.00 (0/0p/1t) | search_database | – |
| prompts | 0.00 / 0.00 / 0.00 (0/8p/2t) | src/backend/fastapi_app/rag_base.py::RAGChatBase.answer_prompt_template; src/backend/fastapi_app/rag_advanced.py::AdvancedRAGChat.query_prompt_template | src/backend/fastapi_app/prompts/answer.txt; src/backend/fastapi_app/prompts/query.txt; evals/generate_ground_truth.py::generate_ground_truth_data#system; src/backend/fastapi_app/rag_advanced.py::AdvancedRAGChat.prepare_context#system; src/backend/fastapi_app/rag_advanced.py::AdvancedRAGChat.answer#system; src/backend/fastapi_app/rag_advanced.py::AdvancedRAGChat.answer_stream#system; src/backend/fastapi_app/rag_simple.py::SimpleRAGChat.answer#system; src/backend/fastapi_app/rag_simple.py::SimpleRAGChat.answer_stream#system |
| workflows | 0.00 / 0.00 / 0.00 (0/1p/2t) | POST /chat; POST /chat/stream | workflow:evals/generate_ground_truth.py::cli:evals/generate_ground_truth.py |
| contradictions | 0.00 / – / 0.00 (0/4p/0t) | – | serving_engine: ['openai', 'ollama']; serving_engine: ['openai', 'ollama']; serving_engine: ['openai', 'ollama']; model: ['gpt-4o-mini', 'llama3.1'] |

Attributes correct: 19/19

### rag-tutorial-v2 (held-out, scan 0.2s)

| category | P / R / F1 (tp/pred/truth) | missed | false positives |
| --- | --- | --- | --- |
| routes | n/a | – | – |
| llm_call_sites | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| models | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| serving_engines | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| retrievers | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| tools | n/a | – | – |
| prompts | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| workflows | – / 0.00 / 0.00 (0/0p/2t) | cli:populate_database.py; cli:query_data.py | – |
| contradictions | n/a | – | – |

Attributes correct: 11/11

### sandbox-conversant-lib (held-out-3, scan 0.9s)

| category | P / R / F1 (tp/pred/truth) | missed | false positives |
| --- | --- | --- | --- |
| routes | n/a | – | – |
| llm_call_sites | 1.00 / 1.00 / 1.00 (2/2p/2t) | – | – |
| models | – / 0.00 / 0.00 (0/0p/2t) | xlarge; command-xlarge-nightly | – |
| serving_engines | – / 0.00 / 0.00 (0/0p/1t) | cohere | – |
| retrievers | n/a | – | – |
| tools | n/a | – | – |
| prompts | n/a | – | – |
| workflows | – / 0.00 / 0.00 (0/0p/1t) | streamlit:conversant/demo/streamlit_example.py | – |
| contradictions | n/a | – | – |

Attributes correct: 12/13; wrong: `rag.present` truth=False pred=True

### tech-trends-chatbot (held-out-4, scan 0.2s)

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

ECE = 0.074 over n = 112 decidable claims.

| confidence bin | n | mean confidence | accuracy |
| --- | ---: | ---: | ---: |
| [0.4, 0.6) | 1 | 0.50 | 0.00 |
| [0.6, 0.8) | 11 | 0.65 | 0.91 |
| [0.8, 1.0) | 100 | 0.95 | 1.00 |
