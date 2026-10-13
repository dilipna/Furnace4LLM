# Held-out set 6: finding correctness (pre-registered labels, frozen scanner 41ca529)

Findings emitted by the product path (reconstruct + Blueprint rules) compared with the expected findings written from source before the first scan. Precision = emitted findings that were expected; recall = expected findings that were emitted. Exact 95% intervals. Labels by the developer agent, not independent. Citation validity and call-site detection are reported separately (`citations.md`, `rq1`).

| app | expected | emitted | matched | precision | recall | excluded rules |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| audiobook-creator | 11 | 28 | 3 | 11% | 27% | 0 |
| BYO-LLM-WIKI | 30 | 26 | 21 | 81% | 70% | 0 |
| mdflux | 5 | 6 | 1 | 17% | 20% | 0 |
| ps-fuzz | 14 | 13 | 10 | 77% | 71% | 0 |
| Soul-of-Waifu | 4 | 4 | 4 | 100% | 100% | 9 |

**Pooled:** precision 39/77 = 51% (39%-62%); recall 39/64 = 61% (48%-73%).

## By rule

| rule | expected | emitted | matched | precision | recall |
| --- | ---: | ---: | ---: | ---: | ---: |
| eval.citation_contract | 1 | 1 | 1 | 100% | 100% |
| eval.grounding_judge | 1 | 3 | 1 | 33% | 100% |
| eval.regression_suite | 4 | 3 | 2 | 67% | 50% |
| inf.prefix_instability | 2 | 1 | 0 | 0% | 0% |
| inf.prefix_stability_guard | 2 | 0 | 0 | n/a | 0% |
| inf.serving_baseline | 1 | 1 | 0 | 0% | 0% |
| obs.genai_tracing | 4 | 1 | 1 | 100% | 25% |
| obs.prompt_versioning | 33 | 33 | 29 | 88% | 88% |
| rel.fallback_gateway | 4 | 3 | 2 | 67% | 50% |
| rel.llm_timeout | 4 | 3 | 3 | 100% | 75% |
| sec.approval_gate_regression_test | 1 | 0 | 0 | n/a | 0% |
| sec.tool_approval_boundary | 7 | 28 | 0 | 0% | 0% |

## Disagreements (for the review; the numbers above stand as computed)

- audiobook-creator: expected, not emitted: `obs.genai_tracing` app
- audiobook-creator: expected, not emitted: `obs.prompt_versioning` {'file': 'utils/add_emotion_tags_to_text.py', 'function': 'enhance_text_with_emotions', 'line': 533}
- audiobook-creator: expected, not emitted: `obs.prompt_versioning` {'file': 'utils/character_extraction_llm.py', 'function': 'extract_character_info_from_batch', 'line': 360}
- audiobook-creator: expected, not emitted: `obs.prompt_versioning` {'file': 'utils/character_extraction_llm.py', 'function': 'identify_speaker_for_dialogue_matching_only', 'line': 764}
- audiobook-creator: expected, not emitted: `obs.prompt_versioning` {'file': 'utils/find_book_protagonist.py', 'function': 'find_book_protagonist_using_search_engine_and_llm', 'line': 241}
- audiobook-creator: expected, not emitted: `inf.prefix_instability` {'file': 'utils/character_extraction_llm.py', 'function': 'extract_character_info_from_batch', 'line': 360}
- audiobook-creator: expected, not emitted: `inf.prefix_instability` {'file': 'utils/character_extraction_llm.py', 'function': 'identify_speaker_for_dialogue_matching_only', 'line': 764}
- audiobook-creator: expected, not emitted: `inf.prefix_stability_guard` {'file': 'utils/add_emotion_tags_to_text.py', 'function': 'enhance_text_with_emotions', 'line': 533}
- audiobook-creator: emitted, not expected: `sec.tool_approval_boundary` (Put a deterministic approval boundary in front of `process_emotion_tags`; ['tool:add_emotion_tags.py::process_emotion_tags'])
- audiobook-creator: emitted, not expected: `sec.tool_approval_boundary` (Put a deterministic approval boundary in front of `extract_text_from_book_using_calibre`; ['tool:book_to_txt.py::extract_text_from_book_using_calibre'])
- audiobook-creator: emitted, not expected: `sec.tool_approval_boundary` (Put a deterministic approval boundary in front of `save_book`; ['tool:book_to_txt.py::save_book'])
- audiobook-creator: emitted, not expected: `sec.tool_approval_boundary` (Put a deterministic approval boundary in front of `process_book_and_extract_text`; ['tool:book_to_txt.py::process_book_and_extract_text'])
- audiobook-creator: emitted, not expected: `sec.tool_approval_boundary` (Put a deterministic approval boundary in front of `main`; ['tool:book_to_txt.py::main'])
- audiobook-creator: emitted, not expected: `sec.tool_approval_boundary` (Put a deterministic approval boundary in front of `generate_audio_with_single_voice`; ['tool:generate_audiobook.py::generate_audio_with_single_voice'])
- audiobook-creator: emitted, not expected: `sec.tool_approval_boundary` (Put a deterministic approval boundary in front of `apply_emotion_tags_to_multi_voice_data`; ['tool:generate_audiobook.py::apply_emotion_tags_to_multi_voice_data'])
- audiobook-creator: emitted, not expected: `sec.tool_approval_boundary` (Put a deterministic approval boundary in front of `process_single_line`; ['tool:generate_audiobook.py::generate_audio_with_single_voice.process_single_line'])
- audiobook-creator: emitted, not expected: `sec.tool_approval_boundary` (Put a deterministic approval boundary in front of `process_single_line`; ['tool:generate_audiobook.py::generate_audio_with_multiple_voices.process_single_line'])
- audiobook-creator: emitted, not expected: `sec.tool_approval_boundary` (Put a deterministic approval boundary in front of `process_book_and_identify_characters`; ['tool:identify_characters_and_output_book_to_jsonl.py::process_book_and_identify_characters'])
- audiobook-creator: emitted, not expected: `sec.tool_approval_boundary` (Put a deterministic approval boundary in front of `main`; ['tool:identify_characters_and_output_book_to_jsonl.py::main'])
- audiobook-creator: emitted, not expected: `sec.tool_approval_boundary` (Put a deterministic approval boundary in front of `add_tags_to_text_chunks`; ['tool:utils/add_emotion_tags_to_text.py::add_tags_to_text_chunks'])
- audiobook-creator: emitted, not expected: `sec.tool_approval_boundary` (Put a deterministic approval boundary in front of `process_emotion_tags_for_jsonl_data`; ['tool:utils/add_emotion_tags_to_text.py::process_emotion_tags_for_jsonl_data'])
- audiobook-creator: emitted, not expected: `sec.tool_approval_boundary` (Put a deterministic approval boundary in front of `generate_chapters_file`; ['tool:utils/audiobook_utils.py::generate_chapters_file'])
- audiobook-creator: emitted, not expected: `sec.tool_approval_boundary` (Put a deterministic approval boundary in front of `merge_chapters_to_m4b`; ['tool:utils/audiobook_utils.py::merge_chapters_to_m4b'])
- audiobook-creator: emitted, not expected: `sec.tool_approval_boundary` (Put a deterministic approval boundary in front of `add_silence_to_audio_file_by_appending_pre_generated_silence`; ['tool:utils/audiobook_utils.py::add_silence_to_audio_file_by_appending_pre_generated_silence'])
- audiobook-creator: emitted, not expected: `sec.tool_approval_boundary` (Put a deterministic approval boundary in front of `merge_chapters_to_standard_audio_file`; ['tool:utils/audiobook_utils.py::merge_chapters_to_standard_audio_file'])
- audiobook-creator: emitted, not expected: `sec.tool_approval_boundary` (Put a deterministic approval boundary in front of `assemble_chapter_with_ffmpeg`; ['tool:utils/audiobook_utils.py::assemble_chapter_with_ffmpeg'])
- audiobook-creator: emitted, not expected: `sec.tool_approval_boundary` (Put a deterministic approval boundary in front of `add_silence_to_chapter_with_ffmpeg`; ['tool:utils/audiobook_utils.py::add_silence_to_chapter_with_ffmpeg'])
- audiobook-creator: emitted, not expected: `sec.tool_approval_boundary` (Put a deterministic approval boundary in front of `empty_file`; ['tool:utils/file_utils.py::empty_file'])
- audiobook-creator: emitted, not expected: `sec.tool_approval_boundary` (Put a deterministic approval boundary in front of `write_json_to_file`; ['tool:utils/file_utils.py::write_json_to_file'])
- audiobook-creator: emitted, not expected: `sec.tool_approval_boundary` (Put a deterministic approval boundary in front of `write_jsons_to_jsonl_file`; ['tool:utils/file_utils.py::write_jsons_to_jsonl_file'])
- audiobook-creator: emitted, not expected: `sec.tool_approval_boundary` (Put a deterministic approval boundary in front of `run_shell_command_secure`; ['tool:utils/run_shell_commands.py::run_shell_command_secure'])
- audiobook-creator: emitted, not expected: `inf.prefix_instability` (Move per-request values out of the start of the system prompt; ['prompt:utils/find_book_protagonist.py::find_book_protagonist_using_search_engine_and_llm#system'])
- audiobook-creator: emitted, not expected: `inf.serving_baseline` (Record a serving baseline: TTFT, TPOT and SLO goodput by concurrency; ['endpoint:generate_audiobook.py::async_openai_client', 'endpoint:identify_characters_and_output_book_to_jsonl.py::async_openai_client', 'endpoint:utils/add_emotion_tags_to_text.py::openai_llm_client'])
- BYO-LLM-WIKI: expected, not emitted: `sec.tool_approval_boundary` {'file': 'kg_tools.py', 'symbol': 'kg_upsert_entity', 'line': 116}
- BYO-LLM-WIKI: expected, not emitted: `sec.tool_approval_boundary` {'file': 'kg_tools.py', 'symbol': 'kg_set_entity_summary', 'line': 137}
- BYO-LLM-WIKI: expected, not emitted: `sec.tool_approval_boundary` {'file': 'kg_tools.py', 'symbol': 'kg_add_relation', 'line': 148}
- BYO-LLM-WIKI: expected, not emitted: `sec.tool_approval_boundary` {'file': 'kg_tools.py', 'symbol': 'kg_merge_entities', 'line': 162}
- BYO-LLM-WIKI: expected, not emitted: `sec.tool_approval_boundary` {'file': 'kg_tools.py', 'symbol': 'kg_upsert_topic', 'line': 176}
- BYO-LLM-WIKI: expected, not emitted: `sec.tool_approval_boundary` {'file': 'kg_tools.py', 'symbol': 'kg_assign_entity_to_topic', 'line': 192}
- BYO-LLM-WIKI: expected, not emitted: `sec.tool_approval_boundary` {'file': 'memory_tools.py', 'symbol': 'memory_write', 'line': 42}
- BYO-LLM-WIKI: expected, not emitted: `sec.approval_gate_regression_test` {'file': 'mcp_tools.py', 'symbol': 'execute_write', 'line': 122}
- BYO-LLM-WIKI: expected, not emitted: `inf.prefix_stability_guard` {'file': 'agent.py', 'symbol': '_BASE_SYSTEM_PROMPT', 'line': 48}
- BYO-LLM-WIKI: emitted, not expected: `eval.regression_suite` (Start a regression suite for LLM behaviour; ['workflow:app.py::POST /api/summarize'])
- BYO-LLM-WIKI: emitted, not expected: `obs.prompt_versioning` (Move `_CROSSDOC_JUDGE` into a versioned prompt file; ['prompt:crossdoc.py::_CROSSDOC_JUDGE'])
- BYO-LLM-WIKI: emitted, not expected: `obs.prompt_versioning` (Move `_REQUIREMENTS` into a versioned prompt file; ['prompt:skill_claude_agent.py::_REQUIREMENTS'])
- BYO-LLM-WIKI: emitted, not expected: `obs.prompt_versioning` (Move `_SKILL_JSON_SHAPE` into a versioned prompt file; ['prompt:skill_claude_agent.py::_SKILL_JSON_SHAPE'])
- BYO-LLM-WIKI: emitted, not expected: `rel.fallback_gateway` (Add retry with backoff, and a fallback endpoint through an existing gateway; [])
- mdflux: expected, not emitted: `rel.fallback_gateway` app
- mdflux: expected, not emitted: `eval.regression_suite` app
- mdflux: expected, not emitted: `obs.genai_tracing` app
- mdflux: expected, not emitted: `inf.serving_baseline` app
- mdflux: emitted, not expected: `sec.tool_approval_boundary` (Put a deterministic approval boundary in front of `_safe_extract_zip`; ['tool:tools/release/extract.py::_safe_extract_zip'])
- mdflux: emitted, not expected: `sec.tool_approval_boundary` (Put a deterministic approval boundary in front of `_run_python`; ['tool:tools/release/runtime_checks.py::_run_python'])
- mdflux: emitted, not expected: `sec.tool_approval_boundary` (Put a deterministic approval boundary in front of `_sidecar_request`; ['tool:tools/release/runtime_checks.py::_sidecar_request'])
- mdflux: emitted, not expected: `sec.tool_approval_boundary` (Put a deterministic approval boundary in front of `terminate_process_tree`; ['tool:tools/release/runtime_checks.py::_sidecar_request.terminate_process_tree'])
- mdflux: emitted, not expected: `eval.grounding_judge` (Add a calibrated grounding judge for answers built from retrieval; [])
- ps-fuzz: expected, not emitted: `rel.llm_timeout` app
- ps-fuzz: expected, not emitted: `rel.fallback_gateway` app
- ps-fuzz: expected, not emitted: `eval.regression_suite` app
- ps-fuzz: expected, not emitted: `obs.genai_tracing` app
- ps-fuzz: emitted, not expected: `sec.tool_approval_boundary` (Put a deterministic approval boundary in front of `save`; ['tool:ps_fuzz/app_config.py::AppConfig.save'])
- ps-fuzz: emitted, not expected: `eval.grounding_judge` (Add a calibrated grounding judge for answers built from retrieval; ['retriever:ps_fuzz/attacks/rag_poisoning.py::TestRAGPoisoning._retrieve_relevant_documents'])
- ps-fuzz: emitted, not expected: `obs.prompt_versioning` (Move `ethical_compliance_template` into a versioned prompt file; ['prompt:ps_fuzz/attacks/ethical_compliance.py::ethical_compliance_template'])
