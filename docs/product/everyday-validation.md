# Installed everyday-model observations

Candidate: Qwen2.5-1.5B Instruct Q4_K_M, Apache-2.0, pinned revision and SHA-256
in the catalog. Installed source `2c250d642a1af2b648b67cb34fd190f535f24d8a`.
These trials do not verify every later build or establish semantic quality.

| Trial | Operational completion | Rule checks | Unscored | Median end-to-end task latency | Observed range |
| --- | --- | --- | --- | --- | --- |
| CPU | 11/11 | 5/9 pass, 4 fail | 2 | 2.500 s | 1.469–10.453 s |
| NVIDIA recipe | 11/11 | 5/9 pass, 4 fail | 2 | 1.781 s | 1.313–5.875 s |

These are individual runs, not a controlled speedup study. Task latency includes local
HTTP, Docker privacy observations and staged processing; it excludes file extraction,
model download and loading. The raw records include per-task latency, request usage,
actual outputs, recipe, Docker allocation and the 4 GiB container request.

Failures remain: the date question included extra prose despite its exact-format rule;
simplification reformatted the date; Spanish punctuation differed from the normalized
expectation. Most seriously, the document-instruction case returned the injected amount
1000 instead of the real invoice total 95. This is a genuine answer/instruction-following
failure. Network isolation is not a prompt-injection or factual-accuracy guarantee.
Missing-information and reply-quality cases remain unscored for human review.

The first GPU attempt failed before inference because Docker was unavailable. It is
retained separately. No model rule, threshold or unfavorable result was removed.

Raw records: [CPU](verification/everyday/everyday-qwen-1.5b-cpu-2c250d6.json),
[NVIDIA](verification/everyday/everyday-qwen-1.5b-gpu-2c250d6-retry.json),
[unavailable Docker](verification/everyday/everyday-gpu-docker-unavailable.json).

The later word-boundary regression fix has unit coverage, but these installed trials
belong to the earlier 2c250d6 candidate. Fresh selected-release acceptance remains a gate.
The model remains a quality-review candidate; it is not approved here for sensitive
professional decisions. Owner/pilot comprehension and quality observations remain blank.
