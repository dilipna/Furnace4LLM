// Conservative setup recommendation, not a guarantee of fit or a model start.
export function recommendedSelection(docker, gpu) {
  const total = gpu?.memory_total_mib, used = gpu?.memory_used_mib;
  const measured = Number.isFinite(total) && Number.isFinite(used) && used >= 0 && used <= total;
  const available = docker?.status === "ready" && docker.gpu_runtime === true && gpu?.name && measured && total >= 4096;
  if (available && total - used >= 3500) return {model: "qwen3-4b-q4_k_m", accelerator: "nvidia"};
  if (available && total - used >= 2048) return {model: "qwen2.5-1.5b-instruct-q4_k_m", accelerator: "nvidia"};
  return {model: "qwen2.5-1.5b-instruct-q4_k_m", accelerator: "cpu"};
}
