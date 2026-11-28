# Why now — evidence and our inference

Reviewed November 27, 2026. Motivation for a hypothesis, not proof of payment demand.

- Open artifacts: the [Hugging Face team](https://huggingface.co/blog/huggingface/state-of-os-hf-spring-2026)
  reports strong growth in artifacts including derivatives/adapters. Greater packaging
  variation is our inference, not an observed customer problem count.
- Architecture boundary: [MDLM's author card](https://huggingface.co/kuleshov-group/mdlm-owt/raw/main/README.md)
  describes masked diffusion; its [config](https://huggingface.co/kuleshov-group/mdlm-owt/raw/main/config.json)
  uses custom code. The [pinned engine inventory](https://raw.githubusercontent.com/ggml-org/llama.cpp/3c809f44383bcebc318b8cddd8c6d11aaa861e9b/src/llama-arch.cpp)
  has no named MDLM entry; [extracted list](engine-inventory.json). This is a specific
  compatibility boundary, not measured support-lag duration or a claim about every
  newer engine. Conversion/serving has not been attempted. Multiple verified
  chronological lag examples are still missing; do not assert an industry-wide delay.
- Execution risk: [Transformers custom-model documentation](https://huggingface.co/docs/transformers/custom_models)
  describes remote-code opt-in; [Hub pickle documentation](https://huggingface.co/docs/hub/security-pickle)
  explains unsafe deserialization/scanning. An opt-in is a trust decision, not proof
  the repository is malicious. Verified bytes and reviewed code are distinct controls.
- Published report verified: [JFrog's original investigation](https://jfrog.com/markdown/blog/data-scientists-targeted-by-malicious-hugging-face-ml-models-with-silent-backdoor.md)
  describes an uploaded model whose pickle loading executes a reverse-shell payload.
  Payload evidence is not proof of named customer compromise or malware prevalence.
  We did not execute or reproduce that malware.
- Reproducibility: the [NeurIPS checklist](https://neurips.cc/public/guides/PaperChecklist)
  asks authors to state experimental reproducibility, claims and limitations. It does
  not endorse Furnace or require purchasing infrastructure.
- Laptop workload: our [Qwen GPU source record](evidence/qwen3-gpu.json) retains failures.
  The [older installed trial](evidence/installed-document.json) was worse on a different
  suite/build. Do not combine scores or call source inference final installed acceptance.

Hypothesis: model execution stays heterogeneous, and researchers may value a reusable
operating/evidence layer. Test with a real outside adapter and actual users.
