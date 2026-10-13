# RQ1: reconstruction accuracy

Deterministic reconstruction only (LLM synthesis is not built, so no +LLM ablation). F1 is the development fixture; held-out apps were labeled from source before their first scan (labels: `bench/ground_truth/`, written by the developer agent, not yet independently reviewed).

## Micro-averaged P / R / F1

| category | F1 (dev) | F2 (dev) | held-out set 1 | held-out set 2 | held-out set 3 | held-out set 4 | held-out set 5 | held-out set 6 |
| --- | --- | --- | --- | --- | --- | --- |
| routes | 1.00 / 1.00 / 1.00 (3/3p/3t) | 1.00 / 1.00 / 1.00 (2/2p/2t) | n/a | 1.00 / 1.00 / 1.00 (2/2p/2t) | n/a | 1.00 / 0.77 / 0.87 (10/10p/13t) | 1.00 / 1.00 / 1.00 (5/5p/5t) | 1.00 / 1.00 / 1.00 (78/78p/78t) |
| llm_call_sites | 1.00 / 1.00 / 1.00 (1/1p/1t) | 1.00 / 1.00 / 1.00 (1/1p/1t) | 1.00 / 1.00 / 1.00 (8/8p/8t) | 1.00 / 1.00 / 1.00 (5/5p/5t) | 1.00 / 0.89 / 0.94 (8/8p/9t) | 1.00 / 1.00 / 1.00 (9/9p/9t) | 1.00 / 1.00 / 1.00 (3/3p/3t) | 1.00 / 0.67 / 0.80 (32/32p/48t) |
| models | 1.00 / 1.00 / 1.00 (1/1p/1t) | 1.00 / 1.00 / 1.00 (1/1p/1t) | 1.00 / 1.00 / 1.00 (4/4p/4t) | 1.00 / 1.00 / 1.00 (2/2p/2t) | 1.00 / 0.18 / 0.30 (3/3p/17t) | – / 0.00 / 0.00 (0/0p/6t) | 1.00 / 0.50 / 0.67 (1/1p/2t) | 1.00 / 0.11 / 0.20 (1/1p/9t) |
| serving_engines | 1.00 / 1.00 / 1.00 (1/1p/1t) | 1.00 / 1.00 / 1.00 (1/1p/1t) | 1.00 / 1.00 / 1.00 (4/4p/4t) | 1.00 / 0.67 / 0.80 (2/2p/3t) | 1.00 / 0.80 / 0.89 (4/4p/5t) | 1.00 / 0.67 / 0.80 (2/2p/3t) | – / 0.00 / 0.00 (0/0p/1t) | 0.00 / 0.00 / 0.00 (0/1p/7t) |
| retrievers | 1.00 / 1.00 / 1.00 (1/1p/1t) | n/a | 1.00 / 1.00 / 1.00 (2/2p/2t) | n/a | 0.67 / 1.00 / 0.80 (2/3p/2t) | – / 0.00 / 0.00 (0/0p/2t) | n/a | 0.00 / 0.00 / 0.00 (0/1p/1t) |
| tools | 1.00 / 1.00 / 1.00 (1/1p/1t) | 0.67 / 0.67 / 0.67 (2/3p/3t) | – / 0.00 / 0.00 (0/0p/1t) | n/a | n/a | – / 0.00 / 0.00 (0/0p/2t) | – / 0.00 / 0.00 (0/0p/11t) | 0.00 / 0.00 / 0.00 (0/28p/23t) |
| prompts | 1.00 / 1.00 / 1.00 (1/1p/1t) | 0.50 / 1.00 / 0.67 (1/2p/1t) | 1.00 / 0.33 / 0.50 (1/1p/3t) | 0.00 / 0.00 / 0.00 (0/3p/4t) | 0.00 / 0.00 / 0.00 (0/2p/2t) | 0.11 / 0.40 / 0.17 (2/19p/5t) | 0.00 / 0.00 / 0.00 (0/4p/8t) | 0.46 / 0.82 / 0.59 (27/59p/33t) |
| workflows | 1.00 / 1.00 / 1.00 (2/2p/2t) | 1.00 / 1.00 / 1.00 (1/1p/1t) | 1.00 / 0.67 / 0.80 (6/6p/9t) | 1.00 / 0.80 / 0.89 (4/4p/5t) | 1.00 / 0.67 / 0.80 (6/6p/9t) | 0.67 / 0.29 / 0.40 (2/3p/7t) | – / 0.00 / 0.00 (0/0p/1t) | – / 0.00 / 0.00 (0/0p/5t) |
| contradictions | 1.00 / 1.00 / 1.00 (1/1p/1t) | – / 0.00 / 0.00 (0/0p/1t) | – / 0.00 / 0.00 (0/0p/1t) | 1.00 / 1.00 / 1.00 (1/1p/1t) | 0.00 / 0.00 / 0.00 (0/3p/2t) | 0.00 / 0.00 / 0.00 (0/4p/1t) | n/a | 0.00 / – / 0.00 (0/7p/0t) |

Attribute accuracy (dev): 13/13 (a scan that finds nothing scores 4/7 on the same truth)

Attribute accuracy (dev-2): 13/13 (a scan that finds nothing scores 6/7 on the same truth)

Attribute accuracy (held-out): 46/46 (a scan that finds nothing scores 15/20 on the same truth)

Attribute accuracy (held-out-2): 27/28 (a scan that finds nothing scores 13/14 on the same truth)

Attribute accuracy (held-out-3): 62/63 (a scan that finds nothing scores 32/35 on the same truth)

Attribute accuracy (held-out-4): 41/42 (a scan that finds nothing scores 15/21 on the same truth)

Attribute accuracy (held-out-5): 15/16 (a scan that finds nothing scores 7/7 on the same truth)

Attribute accuracy (held-out-6): 66/97 (a scan that finds nothing scores 22/33 on the same truth)

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

### agent-actions-py (F2) (dev-2, scan 0.1s)

| category | P / R / F1 (tp/pred/truth) | missed | false positives |
| --- | --- | --- | --- |
| routes | 1.00 / 1.00 / 1.00 (2/2p/2t) | – | – |
| llm_call_sites | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| models | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| serving_engines | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| retrievers | n/a | – | – |
| tools | 0.67 / 0.67 / 0.67 (2/3p/3t) | search_orders | run_agent |
| prompts | 0.50 / 1.00 / 0.67 (1/2p/1t) | – | app/agent.py::run_agent#system |
| workflows | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| contradictions | – / 0.00 / 0.00 (0/0p/1t) | response_cache: ['none', 'redis'] | – |

Attributes correct: 13/13

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

### audiobook-creator (held-out-6, scan 0.6s)

| category | P / R / F1 (tp/pred/truth) | missed | false positives |
| --- | --- | --- | --- |
| routes | n/a | – | – |
| llm_call_sites | 1.00 / 0.60 / 0.75 (3/3p/5t) | utils/character_extraction_llm.py::extract_character_info_from_batch; utils/character_extraction_llm.py::identify_speaker_for_dialogue_matching_only | – |
| models | 1.00 / 0.50 / 0.67 (1/1p/2t) | qwen/qwen3-30b-a3b-instruct-2507 | – |
| serving_engines | 0.00 / 0.00 / 0.00 (0/1p/1t) | openai | vllm |
| retrievers | n/a | – | – |
| tools | 0.00 / – / 0.00 (0/23p/0t) | – | process_emotion_tags; extract_text_from_book_using_calibre; save_book; process_book_and_extract_text; main; generate_audio_with_single_voice; apply_emotion_tags_to_multi_voice_data; process_single_line; process_single_line; process_book_and_identify_characters; main; add_tags_to_text_chunks; process_emotion_tags_for_jsonl_data; generate_chapters_file; merge_chapters_to_m4b; add_silence_to_audio_file_by_appending_pre_generated_silence; merge_chapters_to_standard_audio_file; assemble_chapter_with_ffmpeg; add_silence_to_chapter_with_ffmpeg; empty_file; write_json_to_file; write_jsons_to_jsonl_file; run_shell_command_secure |
| prompts | 0.00 / 0.00 / 0.00 (0/2p/4t) | utils/add_emotion_tags_to_text.py::enhance_text_with_emotions; utils/character_extraction_llm.py::extract_character_info_from_batch; utils/character_extraction_llm.py::identify_speaker_for_dialogue_matching_only; utils/find_book_protagonist.py::find_book_protagonist_using_search_engine_and_llm | utils/add_emotion_tags_to_text.py::enhance_text_with_emotions._call_llm#system; utils/find_book_protagonist.py::find_book_protagonist_using_search_engine_and_llm#system |
| workflows | – / 0.00 / 0.00 (0/0p/3t) | gradio:app.py; cli:identify_characters_and_output_book_to_jsonl.py; cli:add_emotion_tags.py | – |
| contradictions | 0.00 / – / 0.00 (0/5p/0t) | – | serving_engine: ['vllm', 'unknown']; serving_engine: ['vllm', 'unknown']; serving_engine: ['vllm', 'unknown']; serving_engine: ['vllm', 'unknown']; model: ['openai/gpt-oss-20b', 'Qwen3', 'Qwen'] |

Attributes correct: 15/16; wrong: `existing.tracing` truth=False pred=True

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

### BYO-LLM-WIKI (held-out-6, scan 2.2s)

| category | P / R / F1 (tp/pred/truth) | missed | false positives |
| --- | --- | --- | --- |
| routes | 1.00 / 1.00 / 1.00 (64/64p/64t) | – | – |
| llm_call_sites | 1.00 / 0.42 / 0.59 (5/5p/12t) | agent.py::_invoke; enrich.py::_gen; pipeline.py::_gen; rag.py::_gen; skill_agent.py::_gen; skill_eval.py::_gen; skill_runtime.py::run_tool_loop | – |
| models | – / 0.00 / 0.00 (0/0p/6t) | claude-haiku-4-5-20251001; gpt-4o-mini; qwen-plus; deepseek-chat; gemini-3.5-flash; mistral-large-latest | – |
| serving_engines | – / 0.00 / 0.00 (0/0p/2t) | anthropic; openai | – |
| retrievers | – / 0.00 / 0.00 (0/0p/1t) | rag.py::retrieve | – |
| tools | – / 0.00 / 0.00 (0/0p/23t) | kg_stats; kg_search; kg_get_entity; kg_get_chunk; kg_neighbors; kg_list_entities; kg_list_topics; kg_upsert_entity; kg_set_entity_summary; kg_add_relation; kg_merge_entities; kg_upsert_topic; kg_assign_entity_to_topic; memory_recall; memory_write; skill_recall; skill_get; skill_list; read_context; check_draft; list_existing_skills; recall_memory; execute_write | – |
| prompts | 0.86 / 1.00 / 0.92 (18/21p/18t) | – | crossdoc.py::_CROSSDOC_JUDGE; skill_claude_agent.py::_REQUIREMENTS; skill_claude_agent.py::_SKILL_JSON_SHAPE |
| workflows | n/a | – | – |
| contradictions | 0.00 / – / 0.00 (0/1p/0t) | – | model: ['Claude in-process', 'Qwen', 'Claude Code', 'gpt-5.2'] |

Attributes correct: 14/22; wrong: `call.model` truth='claude-haiku-4-5-20251001' pred=None; `call.model` truth='gpt-4o-mini' pred=None; `call.model` truth='claude-haiku-4-5-20251001' pred=None; `call.model` truth='gpt-4o-mini' pred=None; `call.model` truth='claude-haiku-4-5-20251001' pred=None; `existing.timeouts` truth=True pred=False; `existing.retries` truth=True pred=False; `existing.evals` truth=True pred=False

### gemini_multipdf_chat (held-out-3, scan 0.1s)

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

### llama2 (held-out-2, scan 0.1s)

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

### mdflux (held-out-6, scan 2.1s)

| category | P / R / F1 (tp/pred/truth) | missed | false positives |
| --- | --- | --- | --- |
| routes | n/a | – | – |
| llm_call_sites | – / 0.00 / 0.00 (0/0p/3t) | app/src-tauri/resources/sidecar/provider.py::chat_openai_compat; app/src-tauri/resources/sidecar/provider.py::chat_ollama; app/src-tauri/resources/sidecar/provider.py::chat_anthropic | – |
| models | n/a | – | – |
| serving_engines | – / 0.00 / 0.00 (0/0p/3t) | ollama; openai; anthropic | – |
| retrievers | n/a | – | – |
| tools | 0.00 / – / 0.00 (0/4p/0t) | – | _safe_extract_zip; _run_python; _sidecar_request; terminate_process_tree |
| prompts | 0.33 / 1.00 / 0.50 (1/3p/1t) | – | app/src-tauri/resources/sidecar/provider.py::chat_openai_compat#system; app/src-tauri/resources/sidecar/provider.py::chat_ollama#system |
| workflows | – / 0.00 / 0.00 (0/0p/1t) | cli:app/src-tauri/resources/sidecar/main.py | – |
| contradictions | 0.00 / – / 0.00 (0/1p/0t) | – | model: ['DeepSeek', 'Claude Code', 'claude-code'] |

Attributes correct: 5/7; wrong: `rag.present` truth=False pred=True; `existing.timeouts` truth=True pred=False

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

### openai-chat-app-quickstart (held-out-2, scan 0.5s)

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

### openai-chat-backend-fastapi (held-out-4, scan 0.3s)

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

### openai-cs-agents-demo (held-out-5, scan 0.5s)

| category | P / R / F1 (tp/pred/truth) | missed | false positives |
| --- | --- | --- | --- |
| routes | 1.00 / 1.00 / 1.00 (5/5p/5t) | – | – |
| llm_call_sites | 1.00 / 1.00 / 1.00 (3/3p/3t) | – | – |
| models | 1.00 / 0.50 / 0.67 (1/1p/2t) | gpt-5.2 | – |
| serving_engines | – / 0.00 / 0.00 (0/0p/1t) | openai | – |
| retrievers | n/a | – | – |
| tools | – / 0.00 / 0.00 (0/0p/11t) | faq_lookup_tool; get_trip_details; update_seat; flight_status_tool; baggage_tool; get_matching_flights; book_new_flight; assign_special_service_seat; issue_compensation; display_seat_map; cancel_flight | – |
| prompts | 0.00 / 0.00 / 0.00 (0/4p/8t) | python-backend/airline/agents.py::seat_services_instructions; python-backend/airline/agents.py::flight_information_instructions; python-backend/airline/agents.py::booking_cancellation_instructions; python-backend/airline/agents.py::refunds_compensation_instructions; python-backend/airline/agents.py::faq_agent; python-backend/airline/agents.py::triage_agent; python-backend/airline/guardrails.py::guardrail_agent; python-backend/airline/guardrails.py::jailbreak_guardrail_agent | python-backend/airline/agents.py::<module>@Triage_Agent#system; python-backend/airline/agents.py::<module>@FAQ_Agent#system; python-backend/airline/guardrails.py::<module>@Jailbreak_Guardrail#system; python-backend/airline/guardrails.py::<module>@Relevance_Guardrail#system |
| workflows | – / 0.00 / 0.00 (0/0p/1t) | POST /chatkit | – |
| contradictions | n/a | – | – |

Attributes correct: 15/16; wrong: `call.model` truth='gpt-5.2' pred=None

### ps-fuzz (held-out-6, scan 0.9s)

| category | P / R / F1 (tp/pred/truth) | missed | false positives |
| --- | --- | --- | --- |
| routes | n/a | – | – |
| llm_call_sites | – / 0.00 / 0.00 (0/0p/1t) | ps_fuzz/chat_clients.py::ClientLangChain.interact | – |
| models | – / 0.00 / 0.00 (0/0p/1t) | gpt-3.5-turbo | – |
| serving_engines | – / 0.00 / 0.00 (0/0p/1t) | openai | – |
| retrievers | 0.00 / – / 0.00 (0/1p/0t) | – | retriever:ps_fuzz/attacks/rag_poisoning.py::TestRAGPoisoning._retrieve_relevant_documents |
| tools | 0.00 / – / 0.00 (0/1p/0t) | – | save |
| prompts | 0.89 / 0.80 / 0.84 (8/9p/10t) | ps_fuzz/attacks/dynamic_test.py::attack_prompt_gen_template; ps_fuzz/attacks/dynamic_test.py::steal_system_prompt_attack_text | ps_fuzz/attacks/ethical_compliance.py::ethical_compliance_template |
| workflows | – / 0.00 / 0.00 (0/0p/1t) | cli:ps_fuzz/cli.py | – |
| contradictions | n/a | – | – |

Attributes correct: 6/7; wrong: `rag.present` truth=False pred=True

### rag-postgres-openai-python (held-out-4, scan 1.7s)

| category | P / R / F1 (tp/pred/truth) | missed | false positives |
| --- | --- | --- | --- |
| routes | 1.00 / 0.71 / 0.83 (5/5p/7t) | GET /; GET /favicon.ico | – |
| llm_call_sites | 1.00 / 1.00 / 1.00 (6/6p/6t) | – | – |
| models | – / 0.00 / 0.00 (0/0p/4t) | gpt-5.4; gpt-3.5-turbo; phi3:3.8b; llama3.1 | – |
| serving_engines | 1.00 / 1.00 / 1.00 (1/1p/1t) | – | – |
| retrievers | – / 0.00 / 0.00 (0/0p/1t) | src/backend/fastapi_app/postgres_searcher.py::PostgresSearcher.search | – |
| tools | – / 0.00 / 0.00 (0/0p/1t) | search_database | – |
| prompts | 0.00 / 0.00 / 0.00 (0/11p/2t) | src/backend/fastapi_app/rag_base.py::RAGChatBase.answer_prompt_template; src/backend/fastapi_app/rag_advanced.py::AdvancedRAGChat.query_prompt_template | src/backend/fastapi_app/prompts/answer.txt; src/backend/fastapi_app/prompts/query.txt; evals/generate_ground_truth.py::generate_ground_truth_data#system; src/backend/fastapi_app/rag_advanced.py::AdvancedRAGChat.__init__@Answerer#system; src/backend/fastapi_app/rag_advanced.py::AdvancedRAGChat.__init__@Searcher#system; src/backend/fastapi_app/rag_advanced.py::AdvancedRAGChat.prepare_context#system; src/backend/fastapi_app/rag_advanced.py::AdvancedRAGChat.answer#system; src/backend/fastapi_app/rag_advanced.py::AdvancedRAGChat.answer_stream#system; src/backend/fastapi_app/rag_simple.py::SimpleRAGChat.__init__@Answerer#system; src/backend/fastapi_app/rag_simple.py::SimpleRAGChat.answer#system; src/backend/fastapi_app/rag_simple.py::SimpleRAGChat.answer_stream#system |
| workflows | 0.00 / 0.00 / 0.00 (0/1p/2t) | POST /chat; POST /chat/stream | workflow:evals/generate_ground_truth.py::cli:evals/generate_ground_truth.py |
| contradictions | 0.00 / – / 0.00 (0/4p/0t) | – | serving_engine: ['openai', 'ollama']; serving_engine: ['openai', 'ollama']; serving_engine: ['openai', 'ollama']; model: ['gpt-4o-mini', 'llama3.1'] |

Attributes correct: 19/19

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

### sandbox-conversant-lib (held-out-3, scan 0.6s)

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

### Soul-of-Waifu (held-out-6, scan 208.0s)

| category | P / R / F1 (tp/pred/truth) | missed | false positives |
| --- | --- | --- | --- |
| routes | 1.00 / 1.00 / 1.00 (14/14p/14t) | – | – |
| llm_call_sites | 1.00 / 0.89 / 0.94 (24/24p/27t) | app/utils/ai_clients/providers/anthropic_provider.py::AnthropicProvider.generate_stream; app/utils/ai_clients/providers/anthropic_provider.py::AnthropicProvider.generate_summary; app/utils/ai_clients/providers/anthropic_provider.py::AnthropicProvider.generate | – |
| models | n/a | – | – |
| serving_engines | n/a | – | – |
| retrievers | n/a | – | – |
| tools | n/a | – | – |
| prompts | 0.00 / – / 0.00 (0/24p/0t) | – | app/gui/character_ai_assistant.py::CharacterAIAssistantDialog._build_prompt#system; app/gui/interface_signals.py::InterfaceSignals.run_tool_loop#system; app/gui/interface_signals.py::InterfaceSignals.trigger_image_generation#system; app/gui/interface_signals.py::InterfaceSignals._generate_llm_translation#system; app/gui/interface_signals.py::InterfaceSignals._on_soul_stage_launch._ss_translate_fn#system; app/utils/ai_clients/prompt_engine.py::PromptEngine.build_system_prompt_blocks#system; app/utils/ai_clients/prompt_engine.py::PromptEngine.build_system_prompt_blocks#system; app/utils/ai_clients/prompt_engine.py::PromptEngine.build_system_prompt_blocks#system; app/utils/ai_clients/prompt_engine.py::PromptEngine.build_system_prompt_blocks#system; app/utils/ai_clients/prompt_engine.py::PromptEngine.build_summary_prompt_blocks#system; app/utils/ai_clients/soul_stage_engine.py::SoulStageContextWindow.build_for_planner#system; app/utils/ai_clients/soul_stage_engine.py::SoulStageContextWindow.build_for_executor#system; app/utils/ai_clients/soul_stage_engine.py::SoulStageContextWindow.build_for_routing#system; app/utils/ai_clients/soul_stage_engine.py::SoulStageContextWindow.build_for_npc#system; app/utils/ai_clients/soul_stage_engine.py::SoulStageOrchestrator._call_gm_planner#system; app/utils/ai_clients/soul_stage_engine.py::SoulStageOrchestrator._call_gm_executor#system; app/utils/ai_clients/soul_stage_engine.py::SoulStageOrchestrator._call_gm_routing#system; app/utils/ai_clients/soul_stage_engine.py::SoulStageOrchestrator._call_npc#system; app/utils/ai_clients/soul_stage_engine.py::SoulStageOrchestrator._summarize_history#system; app/utils/soul_companion/soul_companion.py::SoulCompanion._llm_call#system; app/utils/soul_companion/soul_companion.py::SoulCompanion._llm_call_stream#system; app/utils/soul_memory.py::SoulMemoryAgent._call_router_agent#system; app/utils/soul_memory.py::SoulMemoryAgent._call_archivist_agent#system; app/utils/soul_memory.py::SoulMemoryAgent._update_daily_diary#system |
| workflows | n/a | – | – |
| contradictions | n/a | – | – |

Attributes correct: 26/45; wrong: `call.streaming` truth=True pred=False; `call.has_timeout` truth=True pred=False; `call.has_timeout` truth=True pred=False; `call.has_timeout` truth=True pred=False; `call.streaming` truth=True pred=False; `call.streaming` truth=True pred=False; `call.has_timeout` truth=True pred=False; `call.has_timeout` truth=True pred=False; `call.has_timeout` truth=True pred=False; `call.streaming` truth=True pred=False; `call.has_timeout` truth=True pred=False; `call.has_timeout` truth=True pred=False; `call.has_timeout` truth=True pred=False; `call.streaming` truth=True pred=False; `call.has_timeout` truth=True pred=False; `call.has_timeout` truth=True pred=False; `call.has_timeout` truth=True pred=False; `existing.tracing` truth=False pred=True; `existing.timeouts` truth=True pred=False

### tech-trends-chatbot (held-out-4, scan 0.9s)

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

ECE = 0.051 over n = 154 decidable claims.

| confidence bin | n | mean confidence | accuracy |
| --- | ---: | ---: | ---: |
| [0.4, 0.6) | 6 | 0.51 | 0.00 |
| [0.6, 0.8) | 15 | 0.65 | 0.93 |
| [0.8, 1.0) | 133 | 0.95 | 0.95 |
