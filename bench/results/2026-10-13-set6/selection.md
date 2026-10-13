# Held-out set 6: selection walk (protocol: docs/scanner-eval-set6.md section 2)

Search run once at the time in `search_time.txt`; raw response `search.json` (175 matches,
first 100 returned). Results walked in order; the first 5 that meet every rule are taken.
File counts: non-test `.py` files at the default-branch head (tests = `tests/`, `test/`,
`test_*.py`, `*_test.py`, `conftest.py`), from the git tree (`trees_1.jsonl` for the first
six, `git ls-tree` on a shallow clone for the rest). Rules 1-3 were decided from file lists,
READMEs and a text search of the source for LLM SDK calls; no Furnace code ran on any of them.

| # | repository | decision | rule / reason |
|---:|---|---|---|
| 1 | LosaLosSantos/aurelio-finance | skip | 3: 89 Python files |
| 2 | e2b-dev/code-interpreter | skip | 1: SDK |
| 3 | vstorm-co/full-stack-ai-agent-template | skip | 1: project generator/template |
| 4 | melih-unsal/DemoGPT | skip | 1: app-generation framework (pip package) |
| 5 | OWASP/www-project-top-10-for-large-language-model-applications | skip | 1: documentation |
| 6 | jofizcd/Soul-of-Waifu | **take** (747048b) | desktop roleplay app; 43 files; OpenAI, Mistral, OpenRouter, Anthropic, Gemini, local LLM backends |
| 7 | langchain-ai/openevals | skip | 1: library |
| 8 | FalkorDB/GraphRAG-SDK | skip | 1: SDK |
| 9 | streamlit/llm-examples | skip | 4: set 1 app |
| 10 | SomeOddCodeGuy/WilmerAI | skip | 3: 126 Python files |
| 11 | pgalko/BambooAI | skip | 3: 109 Python files |
| 12 | prompt-security/ps-fuzz | **take** (9c2138a) | CLI that attacks a system prompt with LLM-generated prompts; 33 files; LangChain chat models |
| 13 | lukaszliniewicz/Pandrator | skip | 3: 816 Python files |
| 14 | avibe-bot/avibe | skip | 3: 507 Python files |
| 15 | baidubce/app-builder | skip | 1: SDK |
| 16 | ibrahimqureshae/mdflux | **take** (00c6025) | desktop app (Tauri) whose Python sidecar converts documents with an LLM provider; 27 files; Python is GitHub's main language |
| 17 | jaylfc/taOS | skip | 3: 720 Python files |
| 18 | StonyBrookNLP/appworld | skip | 1: benchmark |
| 19 | prakharsr/audiobook-creator | **take** (94a353f) | audiobook app; 16 files; OpenAI-compatible chat calls for emotion tags and protagonist detection |
| 20 | Kohaku-Lab/KohakuTerrarium | skip | 1: agent framework |
| 21 | john-rocky/coreai-model-zoo | skip | 1: models |
| 22 | DemonDamon/AgenticX | skip | 1: platform SDK |
| 23 | microsoft/genaiops-promptflow-template | skip | 1: template and guidance |
| 24 | joypaul162/Shubhamsaboo-awesome-llm-apps | skip | 1: collection |
| 25 | meangrinch/MangaTranslator | skip | 3: 63 Python files |
| 26 | aqua5230/usage | skip | 3: 159 Python files |
| 27 | mindroom-ai/mindroom | skip | 3: 1,226 Python files |
| 28 | jia-gao/leanctx | skip | 1: library (also 61 files) |
| 29 | BlueFalconHD/apple_generative_model_safety_decrypted | skip | 1: data files |
| 30 | jin-bo/agentao | skip | 1: agent runtime library |
| 31 | QuantumByteOSS/quantumbyte | skip | 1: app-builder engine |
| 32 | Lyra-stellAI/BYO-LLM-WIKI | **take** (0316fb7) | Flask wiki app with RAG, agents and MCP; 32 files; Anthropic, OpenAI and LangChain calls |

Selection ends at #32. Kept with the selection: commits pinned above (full SHAs in
`bench/ground_truth/<app>.yaml`). Soul-of-Waifu has one GUI module of over 12,000 lines; it
is labeled like the others (skipping it for being hard to label would bias the set).
