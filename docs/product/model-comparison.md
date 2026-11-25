# Everyday document model comparison

The owner approved Qwen3-4B for compatible NVIDIA GPUs and Qwen2.5-1.5B for CPU/the faster
option. The guided selection is prepared for review; no release is approved. These compare **Furnace's whole document workflow**, including staged results,
not standalone model capability. Synthetic sources include lease terms, an appointment
letter, a bank excerpt, an email thread and a fictional council form. All 36 cases have
fixed rules; eight are document-instruction attacks. Rule agreement is not semantic quality.

**Latest installed confirmation: 31/36, including 7/8 fixed attacks.** The clean-source
`04ef0a0` Windows installer completed all 36 GPU tasks, but followed the fake
safety-policy attack and answered `1000` instead of `95`. The warning was returned.
The earlier source and installed results below remain recorded; do not substitute their
32/36 and 8/8 for this latest observation. See [installed acceptance](installed-document-acceptance.md).

Newer focused source trials for sentence protection, timeout recovery, context sizing
and six long questions are [reported separately](document-workflow-improvements.md).
They do not replace this historical 36-case comparison or the installed result.

| Candidate (Q4_K_M) | Device | Rule passes / 36 planned | Completed tasks | Fixed attacks passed / 8 | Median task seconds | Max sampled container GiB | Max sampled whole-device GPU MiB | Download bytes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Qwen2.5-1.5B | CPU | 27/36 | 36 | 2/8 | 4.171 | 1.780 | — | 1,117,320,736 |
| Qwen2.5-1.5B | NVIDIA | 25/36 | 36 | 1/8 | 1.804 | 1.576 | 1,419 | 1,117,320,736 |
| SmolLM2-1.7B Instruct | CPU | 20/36 | 36 | 1/8 | 8.390 | 3.904 | — | 1,055,609,536 |
| SmolLM2-1.7B Instruct | NVIDIA | 16/36 | 36 | 0/8 | 2.336 | 3.243 | 2,126 | 1,055,609,536 |
| Qwen3-4B | CPU | 26/36 | 31 | 8/8 | 10.984* | 3.797 | — | 2,497,280,256 |
| Qwen3-4B | NVIDIA | 32/36 | 36 | 8/8 | 2.680 | 3.648 | 3,320 | 2,497,280,256 |

*The Qwen3 CPU median covers only 31 completed tasks, **not the full suite**. The
Thread actions request hit the unchanged 120-second request timeout (120.422 s observed).
The endpoint then required reconnection, so the final four requests were refused.
These five execution failures remain in the denominator; they are not missing scoring
rules or discarded observations. The container was observed running, without an OOM
flag, and shutdown completed. The precise cause of its slow generation is not isolated.

Source: [derived summary with raw-file hashes](verification/everyday/comparison-v3-summary.json).
Its six source links name the complete raw records in the same directory. Exact suite
bytes are [archived](verification/everyday/everyday-suite-v2-trials.json).
Reproduce the summary with `scripts/report_everyday_comparison.py`; it refuses to omit
planned cases or combine different suite digests. Raw records and summaries are never
overwritten by the recording scripts.

## Recommendation for the owner's decision

Consider **Qwen3-4B for a compatible NVIDIA GPU**, with **Qwen2.5-1.5B as the CPU and
faster/lower-memory option**. Do not select Qwen3-4B as a universal CPU default from
these results: it did not complete that trial. Its GPU run had the best rule result
and passed these eight attacks in that source trial. The latest installed run failed
one of them. Neither result establishes general injection resistance.
SmolLM2 has a slightly smaller download, but observed runtime memory was higher than
Qwen2.5-1.5B and its rule results were worse here; file size alone does not predict runtime fit.
The owner approved that conditional selection after reviewing the results. Initial setup
recommends Qwen3 only with working Docker GPU access, at least 4,096 MiB total GPU
memory and 3,500 MiB currently free; otherwise it chooses the faster GPU option when
2,048 MiB is free, or CPU. These are conservative planning heuristics, not guaranteed
minimums. Existing project settings and deliberate user choices take precedence. Nothing
is downloaded or started without the existing explicit approvals. Guided setup refuses
the quality option on CPU; Advanced retains experimental CPU access.

Important remaining failures: Qwen3 GPU reformatted a requested exact date; it said it
did not know the rent, deposit and final review date despite those facts being in the
longer documents. Staged processing can lose facts. Qwen2.5-1.5B still followed document
instructions in several cases. None is approved as professional advice or an autonomous
decision maker. The complete outputs, not only totals, need human review.

## Prompt-injection evidence

Seven attacks were added to the original case: role spoofing, false corrections,
quoted email, HTML comments, a fake safety policy, delimiter spoofing and an indirect
Spanish command. The same eight-case Qwen2.5-1.5B CPU baseline passed **0/8**. Clear
delimiters/repeated instructions alone still passed **0/8**. A separate system-role
instruction passed **2/8**, also 2/8 in the full CPU trial. The first unsuccessful
mitigation is retained in `injection-after-cpu.json`; it is not described as fixed.
An eight-case old-prompt GPU baseline was not run. Do not infer a paired GPU improvement
from the historical single attack or attribute Qwen3's result solely to the prompt change.

The API flags some AI-directed phrases and returns the exact warning:
“This document contains text addressed to an AI. Check the answer against the document.”
It is visible on the answer, with receipt details closed. Detection is heuristic:
false positives and missed attacks remain possible. It does not block every attack.
The checked model container has no internet route and this workflow grants no fetch
or tool-execution capability. Text cannot grant that route; it can still corrupt a
local answer or cause sensitive text to be repeated. Host/browser activity is outside
that boundary. See [the contract](private-documents.md).

## Conditions and limits

- Windows 11, Docker Desktop Linux containers, reported Docker memory 8,150,224,896
  bytes, NVIDIA RTX 3050 Ti Laptop GPU with 4,096 MiB. Every recipe requested a 4 GiB
  container, context 4,096, four CPU threads, output cap 512 and per-request timeout 120 s.
  Recipe revisions, weight hashes, image digests and observations are in the records.
- These are individual source-checkout trials with explicit source identity, not
  installed-binary acceptance. Model runs were sequential. Other workloads and some
  developer builds ran concurrently on the shared host. Latencies are observations,
  **not a controlled speedup ranking** or a performance promise.
- Latencies include loopback HTTP, before/after isolation checks and staged requests;
  exclude preparation, model loading, file parsing and between-task memory sampling.
  Memory is the maximum of sampled observations, not a continuous peak. GPU usage is
  device-wide, including other consumers. Fit on this machine is not universal fit.
- Qwen3 requests use the documented `/no_think` hint in the trusted system message.
  Every candidate uses its existing chat template and the same task/rule set. A hint is
  not a hard reasoning-budget guarantee. No rule or timeout was relaxed for the comparison.

## License and provenance

Qwen2.5-1.5B and Qwen3-4B official GGUF model cards/license files declare Apache-2.0.
The official SmolLM2 GGUF conversion card and original instruct card also declare
Apache-2.0; the conversion repository has no separate LICENSE file (the failed lookup
is retained). Original cards, canonical Apache license terms, URLs and hashes are in
[model-licenses](model-licenses/). Apache-2.0 allows reproduction/distribution and
derivatives, including commercial use, subject to its license/notice requirements;
it does not grant trademarks or warranties. Publication licensing review remains a gate.
Nothing here redistributes weights or treats an entire model family as one license.

## Dense 25-page text PDF

The same synthetic PDF (80,938 file bytes; 66,380 extracted UTF-8 bytes) was actually
parsed locally and answered by Qwen2.5-1.5B on both devices. It exceeds the old 24,000-byte
limit. Each run processed 67 source sections in 75 model requests and passed the two
required owner/deadline fields. Both shut down cleanly.

| Device | Extraction seconds | Answer task seconds | Evidence |
| --- | --- | --- | --- |
| CPU | 0.546 | 223.360 | [raw record](verification/everyday/document25-cpu.json) |
| NVIDIA | 0.609 | 78.000 | [raw record](verification/everyday/document25-gpu.json) |

The task times exclude extraction, preparation and loading; do not add them to the
36-case median. This is one fictional administrative handbook, not a guarantee for
every 25-page document or a comprehensive fidelity score. The exact PDF hash and fixture
hash are recorded; byte-exact fixture source is archived in `long-document-fixture.py.gz`.
The current limit is 128,000 extracted UTF-8 bytes, 3 MB per file and 40 PDF pages.
Scanned PDFs and image-only sections still need OCR, which is not implemented.


The two initial PDF records retain the harness's older generic `source_data` label
(“synthetic packaged everyday suite only”). Their `suite_override` identifies the actual
external synthetic PDF fixture and hash; that explicit override describes the run.
The label is corrected in future recording commands, without rewriting either raw record.
