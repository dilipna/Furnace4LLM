# RQ1: reconstruction accuracy

Deterministic reconstruction only (LLM synthesis is not built, so no +LLM ablation). F1 is the development fixture; held-out apps were labeled from source before their first scan (labels: `bench/ground_truth/`, written by the developer agent, not yet independently reviewed).

## Micro-averaged P / R / F1

| category | F1 (dev) | held-out (3 apps) |
| --- | --- | --- |
| routes | 1.00 / 1.00 / 1.00 (3/3p/3t) | n/a |
| llm_call_sites | 1.00 / 1.00 / 1.00 (1/1p/1t) | – / 0.00 / 0.00 (0/0p/8t) |
| models | 1.00 / 1.00 / 1.00 (1/1p/1t) | – / 0.00 / 0.00 (0/0p/4t) |
| serving_engines | 1.00 / 1.00 / 1.00 (1/1p/1t) | – / 0.00 / 0.00 (0/0p/4t) |
| retrievers | 1.00 / 1.00 / 1.00 (1/1p/1t) | 1.00 / 0.50 / 0.67 (1/1p/2t) |
| tools | 1.00 / 1.00 / 1.00 (1/1p/1t) | – / 0.00 / 0.00 (0/0p/1t) |
| prompts | 1.00 / 1.00 / 1.00 (1/1p/1t) | 0.20 / 0.33 / 0.25 (1/5p/3t) |
| workflows | 1.00 / 1.00 / 1.00 (2/2p/2t) | – / 0.00 / 0.00 (0/0p/9t) |
| contradictions | 1.00 / 1.00 / 1.00 (1/1p/1t) | – / 0.00 / 0.00 (0/0p/1t) |

Attribute accuracy (dev): 13/13 (a scan that finds nothing scores 4/7 on the same truth)

Attribute accuracy (held-out): 19/22 (a scan that finds nothing scores 15/20 on the same truth)

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
| llm_call_sites | – / 0.00 / 0.00 (0/0p/1t) | app.py::get_conversation_chain | – |
| models | n/a | – | – |
| serving_engines | – / 0.00 / 0.00 (0/0p/1t) | openai | – |
| retrievers | – / 0.00 / 0.00 (0/0p/1t) | app.py::get_vectorstore | – |
| tools | n/a | – | – |
| prompts | 0.00 / – / 0.00 (0/3p/0t) | – | htmlTemplates.py::css; htmlTemplates.py::bot_template; htmlTemplates.py::user_template |
| workflows | – / 0.00 / 0.00 (0/0p/1t) | streamlit:app.py | – |
| contradictions | – / 0.00 / 0.00 (0/0p/1t) | entrypoint: ['app.py', 'main.py'] | – |

Attributes correct: 6/6

### llm-examples (held-out, scan 0.0s)

| category | P / R / F1 (tp/pred/truth) | missed | false positives |
| --- | --- | --- | --- |
| routes | n/a | – | – |
| llm_call_sites | – / 0.00 / 0.00 (0/0p/6t) | Chatbot.py::<module>; pages/1_File_Q&A.py::<module>; pages/2_Chat_with_search.py::<module>; pages/3_Langchain_Quickstart.py::generate_response; pages/4_Langchain_PromptTemplate.py::blog_outline; pages/5_Chat_with_user_feedback.py::<module> | – |
| models | – / 0.00 / 0.00 (0/0p/3t) | gpt-3.5-turbo; claude-v1; text-davinci-003 | – |
| serving_engines | – / 0.00 / 0.00 (0/0p/2t) | openai; anthropic | – |
| retrievers | n/a | – | – |
| tools | – / 0.00 / 0.00 (0/0p/1t) | Search | – |
| prompts | – / 0.00 / 0.00 (0/0p/2t) | pages/1_File_Q&A.py::prompt; pages/4_Langchain_PromptTemplate.py::template | – |
| workflows | – / 0.00 / 0.00 (0/0p/6t) | streamlit:Chatbot.py; streamlit:pages/1_File_Q&A.py; streamlit:pages/2_Chat_with_search.py; streamlit:pages/3_Langchain_Quickstart.py; streamlit:pages/4_Langchain_PromptTemplate.py; streamlit:pages/5_Chat_with_user_feedback.py | – |
| contradictions | n/a | – | – |

Attributes correct: 7/7

### rag-tutorial-v2 (held-out, scan 0.0s)

| category | P / R / F1 (tp/pred/truth) | missed | false positives |
| --- | --- | --- | --- |
| routes | n/a | – | – |
| llm_call_sites | – / 0.00 / 0.00 (0/0p/1t) | query_data.py::query_rag | – |
| models | – / 0.00 / 0.00 (0/0p/1t) | mistral | – |
| serving_engines | – / 0.00 / 0.00 (0/0p/1t) | ollama | – |
| retrievers | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| tools | n/a | – | – |
| prompts | 0.50 / 1.00 / 0.67 (1/2p/1t) | – | test_rag.py::EVAL_PROMPT |
| workflows | – / 0.00 / 0.00 (0/0p/2t) | cli:populate_database.py; cli:query_data.py | – |
| contradictions | n/a | – | – |

Attributes correct: 6/9; wrong: `retriever.store` truth='chroma' pred='vector'; `retriever.top_k` truth=5 pred=None; `existing.evals` truth=True pred=False

## Confidence calibration (all apps)

ECE = 0.082 over n = 12 decidable claims.

| confidence bin | n | mean confidence | accuracy |
| --- | ---: | ---: | ---: |
| [0.6, 0.8) | 2 | 0.65 | 1.00 |
| [0.8, 1.0) | 10 | 0.93 | 0.90 |
