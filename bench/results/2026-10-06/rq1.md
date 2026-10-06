# RQ1: reconstruction accuracy

Deterministic reconstruction only (LLM synthesis is not built, so no +LLM ablation). F1 is the development fixture; held-out apps were labeled from source before their first scan (labels: `bench/ground_truth/`, written by the developer agent, not yet independently reviewed).

## Micro-averaged P / R / F1

| category | F1 (dev) | held-out set 1 | held-out set 2 |
| --- | --- | --- | --- |
| routes | 1.00 / 1.00 / 1.00 (3/3p/3t) | n/a | 1.00 / 1.00 / 1.00 (2/2p/2t) |
| llm_call_sites | 1.00 / 1.00 / 1.00 (1/1p/1t) | 1.00 / 1.00 / 1.00 (8/8p/8t) | 1.00 / 0.20 / 0.33 (1/1p/5t) |
| models | 1.00 / 1.00 / 1.00 (1/1p/1t) | 1.00 / 1.00 / 1.00 (4/4p/4t) | – / 0.00 / 0.00 (0/0p/2t) |
| serving_engines | 1.00 / 1.00 / 1.00 (1/1p/1t) | 1.00 / 1.00 / 1.00 (4/4p/4t) | – / 0.00 / 0.00 (0/0p/3t) |
| retrievers | 1.00 / 1.00 / 1.00 (1/1p/1t) | 1.00 / 1.00 / 1.00 (2/2p/2t) | n/a |
| tools | 1.00 / 1.00 / 1.00 (1/1p/1t) | – / 0.00 / 0.00 (0/0p/1t) | n/a |
| prompts | 1.00 / 1.00 / 1.00 (1/1p/1t) | 1.00 / 0.33 / 0.50 (1/1p/3t) | 0.00 / 0.00 / 0.00 (0/3p/4t) |
| workflows | 1.00 / 1.00 / 1.00 (2/2p/2t) | – / 0.00 / 0.00 (0/0p/9t) | 1.00 / 0.20 / 0.33 (1/1p/5t) |
| contradictions | 1.00 / 1.00 / 1.00 (1/1p/1t) | – / 0.00 / 0.00 (0/0p/1t) | 0.00 / 0.00 / 0.00 (0/1p/1t) |

Attribute accuracy (dev): 13/13 (a scan that finds nothing scores 4/7 on the same truth)

Attribute accuracy (held-out): 46/46 (a scan that finds nothing scores 15/20 on the same truth)

Attribute accuracy (held-out-2): 15/16 (a scan that finds nothing scores 13/14 on the same truth)

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

### llama2 (held-out-2, scan 0.0s)

| category | P / R / F1 (tp/pred/truth) | missed | false positives |
| --- | --- | --- | --- |
| routes | n/a | – | – |
| llm_call_sites | – / 0.00 / 0.00 (0/0p/4t) | streamlit_app.py::generate_llama2_response; streamlit_app_v2.py::generate_llama2_response; app_v1.py::generate_llama2_response; llama2-local.py::<module> | – |
| models | – / 0.00 / 0.00 (0/0p/2t) | a16z-infra/llama13b-v2-chat; llama-2-7b-chat.ggmlv3.q2_k.bin | – |
| serving_engines | – / 0.00 / 0.00 (0/0p/2t) | replicate; llama_cpp | – |
| retrievers | n/a | – | – |
| tools | n/a | – | – |
| prompts | – / 0.00 / 0.00 (0/0p/3t) | streamlit_app.py::string_dialogue; streamlit_app_v2.py::string_dialogue; app_v1.py::string_dialogue | – |
| workflows | – / 0.00 / 0.00 (0/0p/4t) | streamlit:streamlit_app.py; streamlit:streamlit_app_v2.py; streamlit:app_v1.py; cli:llama2-local.py | – |
| contradictions | 0.00 / 0.00 / 0.00 (0/1p/1t) | model: ['Llama2-7B', 'a16z-infra/llama13b-v2-chat'] | model: ['Llama 2', 'Llama2-7B', 'llama2-chatbot', 'llama2.streamlitapp.com', 'Llama2-13B', 'Llama2-70B'] |

Attributes correct: 7/7

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
| workflows | – / 0.00 / 0.00 (0/0p/6t) | streamlit:Chatbot.py; streamlit:pages/1_File_Q&A.py; streamlit:pages/2_Chat_with_search.py; streamlit:pages/3_Langchain_Quickstart.py; streamlit:pages/4_Langchain_PromptTemplate.py; streamlit:pages/5_Chat_with_user_feedback.py | – |
| contradictions | n/a | – | – |

Attributes correct: 25/25

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

### rag-tutorial-v2 (held-out, scan 0.1s)

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

## Confidence calibration (all apps)

ECE = 0.054 over n = 45 decidable claims.

| confidence bin | n | mean confidence | accuracy |
| --- | ---: | ---: | ---: |
| [0.6, 0.8) | 4 | 0.66 | 0.75 |
| [0.8, 1.0) | 41 | 0.95 | 1.00 |
