# RQ1: reconstruction accuracy

Deterministic reconstruction only (LLM synthesis is not built, so no +LLM ablation). F1 is the development fixture; held-out apps were labeled from source before their first scan (labels: `bench/ground_truth/`, written by the developer agent, not yet independently reviewed).

## Micro-averaged P / R / F1

| category | F1 (dev) | held-out set 1 | held-out set 2 |
| --- | --- | --- | --- |

Attribute accuracy (held-out-2): 15/16 (a scan that finds nothing scores 13/14 on the same truth)

## Per app

### llama2 (held-out-2, scan 0.1s)

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

### openai-chat-app-quickstart (held-out-2, scan 0.8s)

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

## Confidence calibration (all apps)

ECE = 0.133 over n = 3 decidable claims.

| confidence bin | n | mean confidence | accuracy |
| --- | ---: | ---: | ---: |
| [0.6, 0.8) | 2 | 0.68 | 0.50 |
| [0.8, 1.0) | 1 | 0.95 | 1.00 |
