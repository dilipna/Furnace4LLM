# Scanner metrics, reconciled (2026-10-12)

Every number below is a ratio of counts from stored scorer output. Unit, dataset and denominator are stated for each. Labels were written by the developer agent from source at pinned commits, before the first scan of each set; **no label was independently reviewed.**

## Definitions

- **Call-site detection** (RQ1 `llm_call_sites`): unit = one labeled LLM call site, identified by file + function (a label of `<module>` matches any prediction in that file). TP = a label matched one-to-one by a predicted site; FP = predicted site with no label; FN = label with no predicted site. Precision = TP/(TP+FP), recall = TP/(TP+FN).
- **Citation accuracy**: unit = one evidence item attached to a Blueprint finding; correct if the cited file exists and (for line-ranged evidence) the range contains the excerpt. It says nothing about whether the finding is right or whether a true finding was found (`bench/external_validation.py`, stored in `2026-10-11-external\external_validation_first_run.json`).
- **Finding detection** (Blueprint recommendations): **not measured.** No labeled set of expected findings exists for any app, so there is no finding-level TP/FP/FN. Findings are derived from the call sites, prompts and attributes scored above, so a missed call site also silently removes the findings that depend on it.

## 1. Call-site detection, first scan of each set (the held-out figure)

| set | scanner state | TP | FP | FN | predicted (TP+FP) | labeled (TP+FN) | precision | recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| set 1 | scanner at 979350b, first scan 2026-10-06 | 0 | 0 | 8 | 0 | 8 | n/a | 0.00 |
| set 2 | scanner after the set-1 fix, 2026-10-06 | 1 | 0 | 4 | 1 | 5 | 1.00 | 0.20 |
| set 3 | scanner 7fe8c79 (unchanged since labels 129103c) | 1 | 0 | 8 | 1 | 9 | 1.00 | 0.11 |
| set 4 | scanner unchanged since labels f0fce9d | 2 | 0 | 7 | 2 | 9 | 1.00 | 0.22 |
| set 5 | scanner unchanged since labels f038d20 | 0 | 0 | 3 | 0 | 3 | n/a | 0.00 |
| **pooled** | mixed scanner states | 4 | 0 | 30 | 4 | 34 | 1.00 | 0.12 |

Pooled first-scan recall 0.12 (4/34; 95% CI 0.05-0.27); precision 1.00 (4/4; 95% CI 0.51-1.00). The precision denominator is **4 predicted sites**: sets 1 and 5 produced none, so "1.00" on first scans rests on four predictions and its 95% lower bound is about 0.51. The set-4 figure the audit quoted (**2/9 recall**) is row 'set 4': TP 2, FP 0, FN 7 over 3 apps and 9 labeled sites (2 + 6 + 1).

Missed call sites at first scan, with the API each label names (read from the label files):

- set 1, `ask-multiple-pdfs`: 1/1 missed; labeled API of the missed sites: langchain.chat_models.ChatOpenAI (via ConversationalRetrievalChain)
- set 1, `llm-examples`: 6/6 missed; labeled API of the missed sites: anthropic.completions.create; langchain ChatOpenAI via agent.run; langchain.llms.OpenAI.__call__; openai.chat.completions.create
- set 1, `rag-tutorial-v2`: 1/1 missed; labeled API of the missed sites: langchain_community.llms.ollama.Ollama.invoke
- set 2, `llama2`: 4/4 missed; labeled API of the missed sites: llama_cpp.Llama.__call__; replicate.run
- set 3, `Bedrock-ChatBot-with-LangChain-and-Streamlit`: 4/4 missed; labeled API of the missed sites: langchain.Bedrock (via ConversationChain); langchain.BedrockChat (via ConversationChain); langchain.ChatBedrockConverse (via RunnableWithMessageHistory)
- set 3, `llamav2-chat`: 1/1 missed; labeled API of the missed sites: replicate.run
- set 3, `mistral-streamlit-chat`: 1/1 missed; labeled API of the missed sites: mistralai.MistralClient.chat_stream
- set 3, `sandbox-conversant-lib`: 2/2 missed; labeled API of the missed sites: cohere.Client.generate
- set 4, `openai-chat-backend-fastapi`: 2/2 missed; labeled API of the missed sites: openai.AsyncOpenAI.responses.create (client from globals.clients["openai"]); openai.AsyncOpenAI.responses.create(stream=True)
- set 4, `rag-postgres-openai-python`: 5/6 missed; labeled API of the missed sites: agents.Runner.run; agents.Runner.run (OpenAI Agents SDK, OpenAIResponsesModel over AsyncOpenAI); agents.Runner.run (search agent with a function tool); agents.Runner.run_streamed
- set 5, `openai-cs-agents-demo`: 3/3 missed; labeled API of the missed sites: agents.Runner.run; agents.Runner.run (guardrail agent, structured output); agents.Runner.run_streamed (triage agent with handoffs)

Pattern summary (set 4 and 5, the newest): (a) frameworks that hide the SDK call behind an agent runner (OpenAI Agents SDK `Runner.run*`: 5 of 7 missed sites in set 4, 3 of 3 in set 5), and (b) clients reached through a container (`clients['openai']`: 2 of 7). Earlier sets: unsupported SDKs (Replicate, Mistral, Cohere, Bedrock, llama.cpp) and module-level script calls.

## 2. The same labels, current scanner (development-set numbers, NOT held-out)

Sets 1-5 were each used to decide a scanner change after their first scan (commits 261b771, 80cb760, 7a3b431 and later). Scoring today's scanner on them measures how well the fixes fit those apps. It does not predict performance on a new app.

| set | TP | FP | FN | predicted | labeled | precision | recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| set 1 | 8 | 0 | 0 | 8 | 8 | 1.00 | 1.00 |
| set 2 | 5 | 0 | 0 | 5 | 5 | 1.00 | 1.00 |
| set 3 | 8 | 0 | 1 | 8 | 9 | 1.00 | 0.89 |
| set 4 | 9 | 0 | 0 | 9 | 9 | 1.00 | 1.00 |
| set 5 | 3 | 0 | 0 | 3 | 3 | 1.00 | 1.00 |
| **pooled** | 33 | 0 | 1 | 33 | 34 | 1.00 | 0.97 |

## 3. Every category, pooled over sets 1-5

Precision and recall per category (TP, FP, FN, denominators in parentheses). **"Precision 1.00" holds for call sites and routes only.** Prompts, workflows and contradictions produce false positives on the current scanner.

| category | first scan (held-out) | current scanner (dev set) |
| --- | ---: | ---: |
| llm_call_sites | P 100% (4/4), R 12% (4/34) | P 100% (33/33), R 97% (33/34) |
| routes | P 100% (17/17), R 85% (17/20) | P 100% (17/17), R 85% (17/20) |
| models | P 100% (1/1), R 3% (1/31) | P 100% (10/10), R 32% (10/31) |
| serving_engines | P 100% (2/2), R 12% (2/16) | P 100% (12/12), R 75% (12/16) |
| retrievers | P 75% (3/4), R 50% (3/6) | P 80% (4/5), R 67% (4/6) |
| tools | P n/a (0/0), R 0% (0/14) | P n/a (0/0), R 0% (0/14) |
| prompts | P 12% (3/26), R 14% (3/22) | P 10% (3/29), R 14% (3/22) |
| workflows | P 50% (1/2), R 3% (1/31) | P 95% (18/19), R 58% (18/31) |
| contradictions | P 0% (0/8), R 0% (0/5) | P 12% (1/8), R 20% (1/5) |

Notes: `routes` are scored only on sets 2, 4 and 5 (sets 1 and 3 label no routes); no scanner change touched routes, so first-scan and current agree. The scorer matches prompts by `file::symbol`; on sets 4 and 5 the scanner reports prompt *files* and per-call system slots while the labels name Python attributes, so prompt precision there is low partly by labeling convention (disclosed in `2026-10-11-external/NOTES.md`; the labels were not changed after the scan).

## 4. Citation accuracy (a different quantity)

The check covers **every** evidence item of every Blueprint finding (no sampling). First run on held-out set 4 (3 apps): 11 findings, 10 evidence items, 10 resolved, 0 broken (`external_validation_first_run.md`; that run did not record how many items were file-level). Current scanner, same 3 apps (`2026-10-12-reconcile/external_validation.md`): 15 findings, 20 evidence items, 0 broken, of which 1 is file-level evidence that passes on file existence alone. A line-ranged item passes when the file exists, the range is inside it and the first 60 characters of the scanner's own excerpt appear within one line of the range. So this is **internal consistency of evidence links**; it is not finding precision (no finding was judged correct or incorrect) and not finding recall. It is the audit's "10/10".

## 5. What may be claimed

- Call-site detection on apps the scanner had not seen: recall 4/34 (12%, 95% CI 5-27%), precision 4/4. Range across sets: 0% to 22%.
- After set-specific fixes, the same 34 labeled sites: recall 33/34, precision 33/33. That is fit to those apps; the 95% lower bound on precision is 0.90, and it says nothing about unseen apps.
- "1.00 precision" must always carry: call sites only, n predicted = 33 (4 on first scan), labels by the developer agent, scanner tuned on the same apps.
- Held-out recall has been below 30% on three of the last three first scans (sets 3, 4, 5: 11%, 22%, 0%). Generalization of recall is not established.
