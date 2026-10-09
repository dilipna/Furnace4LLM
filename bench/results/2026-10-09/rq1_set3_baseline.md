# RQ1: reconstruction accuracy

Deterministic reconstruction only (LLM synthesis is not built, so no +LLM ablation). F1 is the development fixture; held-out apps were labeled from source before their first scan (labels: `bench/ground_truth/`, written by the developer agent, not yet independently reviewed).

## Micro-averaged P / R / F1

| category | F1 (dev) | held-out set 1 | held-out set 2 | held-out set 3 |
| --- | --- | --- | --- | --- |
| routes | – | – | – | n/a |
| llm_call_sites | – | – | – | 1.00 / 0.11 / 0.20 (1/1p/9t) |
| models | – | – | – | 1.00 / 0.06 / 0.11 (1/1p/17t) |
| serving_engines | – | – | – | – / 0.00 / 0.00 (0/0p/5t) |
| retrievers | – | – | – | 0.67 / 1.00 / 0.80 (2/3p/2t) |
| tools | – | – | – | n/a |
| prompts | – | – | – | 0.00 / 0.00 / 0.00 (0/2p/2t) |
| workflows | – | – | – | – / 0.00 / 0.00 (0/0p/9t) |
| contradictions | – | – | – | 0.00 / 0.00 / 0.00 (0/3p/2t) |

Attribute accuracy (held-out-3): 40/42 (a scan that finds nothing scores 32/35 on the same truth)

## Per app

### Bedrock-ChatBot-with-LangChain-and-Streamlit (held-out-3, scan 0.1s)

| category | P / R / F1 (tp/pred/truth) | missed | false positives |
| --- | --- | --- | --- |
| routes | n/a | – | – |
| llm_call_sites | – / 0.00 / 0.00 (0/0p/4t) | bedrock/models.py::ChatModel.__init__; container/app.py::init_conversationchain; simple/bedrock_chatbot.py::init_conversationchain; streaming/bedrock_simple.py::init_conversationchain | – |
| models | – / 0.00 / 0.00 (0/0p/10t) | anthropic.claude-v2; anthropic.claude-3-sonnet-20240229-v1:0; anthropic.claude-3-haiku-20240307-v1:0; mistral.mistral-large-2402-v1:0; us.deepseek.r1-v1:0; us.anthropic.claude-3-7-sonnet-20250219-v1:0; anthropic.claude-3-5-haiku-20241022-v1:0; us.amazon.nova-pro-v1:0; us.amazon.nova-lite-v1:0; us.amazon.nova-micro-v1:0 | – |
| serving_engines | – / 0.00 / 0.00 (0/0p/1t) | bedrock | – |
| retrievers | 0.50 / 1.00 / 0.67 (1/2p/1t) | – | retriever:bedrock/bedrock_embedder.py::rag_search |
| tools | n/a | – | – |
| prompts | 0.00 / 0.00 / 0.00 (0/2p/1t) | bedrock/role_prompt.py | simple/bedrock_chatbot.py::DEFAULT_CLAUDE_TEMPLATE; streaming/bedrock_simple.py::DEFAULT_CLAUDE_TEMPLATE |
| workflows | – / 0.00 / 0.00 (0/0p/5t) | streamlit:bedrock/bedrock_chatbot.py; streamlit:container/app.py; streamlit:simple/bedrock_chatbot.py; streamlit:streaming/bedrock_simple.py; cli:bedrock_indexer.py | – |
| contradictions | 0.00 / 0.00 / 0.00 (0/1p/1t) | entrypoint: ['bedrock/bedrock_chatbot.py', 'bedrock_chatbot_claude_3_sonnet_vision.py', 'bedrock_chatbot_claude_3_sonnet.py'] | model: ['Claude 3', 'DeepSeek', 'claude-3-langchain-streamlit', 'Claude itself'] |

Attributes correct: 9/9

### gemini_multipdf_chat (held-out-3, scan 0.0s)

| category | P / R / F1 (tp/pred/truth) | missed | false positives |
| --- | --- | --- | --- |
| routes | n/a | – | – |
| llm_call_sites | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| models | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| serving_engines | – / 0.00 / 0.00 (0/0p/1t) | google | – |
| retrievers | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| tools | n/a | – | – |
| prompts | – / 0.00 / 0.00 (0/0p/1t) | app.py::get_conversational_chain | – |
| workflows | – / 0.00 / 0.00 (0/0p/1t) | streamlit:app.py | – |
| contradictions | 0.00 / 0.00 / 0.00 (0/1p/1t) | entrypoint: ['app.py', 'main.py'] | model: ['Gemini', 'gemini-pro', 'gemini_multipdf_chat', 'gemini_multipdf_chat.git', 'gemini-pdf-chatbot.git'] |

Attributes correct: 12/12

### llamav2-chat (held-out-3, scan 0.0s)

| category | P / R / F1 (tp/pred/truth) | missed | false positives |
| --- | --- | --- | --- |
| routes | n/a | – | – |
| llm_call_sites | – / 0.00 / 0.00 (0/0p/1t) | main.py::generate_response | – |
| models | – / 0.00 / 0.00 (0/0p/1t) | replicate/llama70b-v2-chat | – |
| serving_engines | – / 0.00 / 0.00 (0/0p/1t) | replicate | – |
| retrievers | n/a | – | – |
| tools | n/a | – | – |
| prompts | n/a | – | – |
| workflows | – / 0.00 / 0.00 (0/0p/1t) | streamlit:main.py | – |
| contradictions | n/a | – | – |

Attributes correct: 6/7; wrong: `existing.retries` truth=False pred=True

### mistral-streamlit-chat (held-out-3, scan 0.0s)

| category | P / R / F1 (tp/pred/truth) | missed | false positives |
| --- | --- | --- | --- |
| routes | n/a | – | – |
| llm_call_sites | – / 0.00 / 0.00 (0/0p/1t) | mistral_chat.py::<module> | – |
| models | – / 0.00 / 0.00 (0/0p/3t) | mistral-tiny; mistral-small; mistral-medium | – |
| serving_engines | – / 0.00 / 0.00 (0/0p/1t) | mistral | – |
| retrievers | n/a | – | – |
| tools | n/a | – | – |
| prompts | n/a | – | – |
| workflows | – / 0.00 / 0.00 (0/0p/1t) | streamlit:mistral_chat.py | – |
| contradictions | 0.00 / – / 0.00 (0/1p/0t) | – | model: ['Mistral', 'mistral-streamlit-chat.git', 'mistral-streamlit-chat', 'MISTRAL_API_KEY', 'mistral_chat.py'] |

Attributes correct: 7/7

### sandbox-conversant-lib (held-out-3, scan 0.1s)

| category | P / R / F1 (tp/pred/truth) | missed | false positives |
| --- | --- | --- | --- |
| routes | n/a | – | – |
| llm_call_sites | – / 0.00 / 0.00 (0/0p/2t) | conversant/prompt_chatbot.py::PromptChatbot.reply; conversant/prompt_chatbot.py::PromptChatbot._dispatch_concurrent_generate_call | – |
| models | – / 0.00 / 0.00 (0/0p/2t) | xlarge; command-xlarge-nightly | – |
| serving_engines | – / 0.00 / 0.00 (0/0p/1t) | cohere | – |
| retrievers | n/a | – | – |
| tools | n/a | – | – |
| prompts | n/a | – | – |
| workflows | – / 0.00 / 0.00 (0/0p/1t) | streamlit:conversant/demo/streamlit_example.py | – |
| contradictions | n/a | – | – |

Attributes correct: 6/7; wrong: `rag.present` truth=False pred=True

## Confidence calibration (all apps)

ECE = 0.156 over n = 10 decidable claims.

| confidence bin | n | mean confidence | accuracy |
| --- | ---: | ---: | ---: |
| [0.4, 0.6) | 1 | 0.50 | 0.00 |
| [0.6, 0.8) | 2 | 0.60 | 1.00 |
| [0.8, 1.0) | 7 | 0.96 | 1.00 |
