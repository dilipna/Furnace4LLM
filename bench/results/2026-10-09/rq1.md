# RQ1: reconstruction accuracy

Deterministic reconstruction only (LLM synthesis is not built, so no +LLM ablation). F1 is the development fixture; held-out apps were labeled from source before their first scan (labels: `bench/ground_truth/`, written by the developer agent, not yet independently reviewed).

## Micro-averaged P / R / F1

| category | F1 (dev) | held-out set 1 | held-out set 2 | held-out set 3 |
| --- | --- | --- | --- | --- |
| routes | 1.00 / 1.00 / 1.00 (3/3p/3t) | n/a | 1.00 / 1.00 / 1.00 (2/2p/2t) | n/a |
| llm_call_sites | 1.00 / 1.00 / 1.00 (1/1p/1t) | 1.00 / 1.00 / 1.00 (8/8p/8t) | 1.00 / 1.00 / 1.00 (5/5p/5t) | 1.00 / 0.89 / 0.94 (8/8p/9t) |
| models | 1.00 / 1.00 / 1.00 (1/1p/1t) | 1.00 / 1.00 / 1.00 (4/4p/4t) | 1.00 / 1.00 / 1.00 (2/2p/2t) | 1.00 / 0.18 / 0.30 (3/3p/17t) |
| serving_engines | 1.00 / 1.00 / 1.00 (1/1p/1t) | 1.00 / 1.00 / 1.00 (4/4p/4t) | 1.00 / 0.67 / 0.80 (2/2p/3t) | 1.00 / 0.80 / 0.89 (4/4p/5t) |
| retrievers | 1.00 / 1.00 / 1.00 (1/1p/1t) | 1.00 / 1.00 / 1.00 (2/2p/2t) | n/a | 0.67 / 1.00 / 0.80 (2/3p/2t) |
| tools | 1.00 / 1.00 / 1.00 (1/1p/1t) | – / 0.00 / 0.00 (0/0p/1t) | n/a | n/a |
| prompts | 1.00 / 1.00 / 1.00 (1/1p/1t) | 1.00 / 0.33 / 0.50 (1/1p/3t) | 0.00 / 0.00 / 0.00 (0/3p/4t) | 0.00 / 0.00 / 0.00 (0/2p/2t) |
| workflows | 1.00 / 1.00 / 1.00 (2/2p/2t) | 1.00 / 0.67 / 0.80 (6/6p/9t) | 1.00 / 0.80 / 0.89 (4/4p/5t) | 1.00 / 0.67 / 0.80 (6/6p/9t) |
| contradictions | 1.00 / 1.00 / 1.00 (1/1p/1t) | – / 0.00 / 0.00 (0/0p/1t) | 1.00 / 1.00 / 1.00 (1/1p/1t) | 0.00 / 0.00 / 0.00 (0/3p/2t) |

Attribute accuracy (dev): 13/13 (a scan that finds nothing scores 4/7 on the same truth)

Attribute accuracy (held-out): 46/46 (a scan that finds nothing scores 15/20 on the same truth)

Attribute accuracy (held-out-2): 27/28 (a scan that finds nothing scores 13/14 on the same truth)

Attribute accuracy (held-out-3): 61/63 (a scan that finds nothing scores 32/35 on the same truth)

## Per app

### support-rag-py (F1) (dev, scan 0.7s)

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

### ask-multiple-pdfs (held-out, scan 0.0s)

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

### Bedrock-ChatBot-with-LangChain-and-Streamlit (held-out-3, scan 0.2s)

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

### gemini_multipdf_chat (held-out-3, scan 0.0s)

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

### llama2 (held-out-2, scan 0.0s)

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

### llamav2-chat (held-out-3, scan 0.0s)

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

Attributes correct: 9/10; wrong: `existing.retries` truth=False pred=True

### llm-examples (held-out, scan 0.0s)

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

### openai-chat-app-quickstart (held-out-2, scan 0.1s)

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

### rag-tutorial-v2 (held-out, scan 0.0s)

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

### sandbox-conversant-lib (held-out-3, scan 0.4s)

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

## Confidence calibration (all apps)

ECE = 0.064 over n = 88 decidable claims.

| confidence bin | n | mean confidence | accuracy |
| --- | ---: | ---: | ---: |
| [0.4, 0.6) | 1 | 0.50 | 0.00 |
| [0.6, 0.8) | 6 | 0.64 | 0.83 |
| [0.8, 1.0) | 81 | 0.95 | 1.00 |
