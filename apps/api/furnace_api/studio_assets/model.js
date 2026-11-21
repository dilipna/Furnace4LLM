import {mergeProjectRecord, requestOutputFor} from "./studio-state.mjs";
const $ = selector => document.querySelector(selector);
const fragment = new URLSearchParams(location.hash.slice(1)).get("session");
const token = fragment || sessionStorage.getItem("furnace-session") || "";
if (fragment) { sessionStorage.setItem("furnace-session", fragment); history.replaceState(null, "", "/model"); }
let projects = [], selected = null, busy = false, refreshing = false;
let refreshGeneration = 0;
let catalog = null, managedPoll = null;
const drafts = new Map(), outputs = new Map(), prompts = new Map();
function notice(value) { $("#model-notice").textContent = value; }
function readableError(reason) {
  const messages = {
    explicit_local_endpoint_consent_required: "Confirm that you operate this endpoint before connecting.",
    configure_local_endpoint_first: "Save your local server settings before connecting.",
    connect_current_model_configuration_first: "Connect again using the current saved project settings.",
    configured_model_not_advertised: "The server does not advertise this exact model ID. Check its model list and your saved settings.",
    endpoint_timeout: "The local server exceeded the request deadline. Reconnect before trying again.",
    endpoint_unavailable_or_invalid: "The local server could not return valid JSON. Check that it is running and supports this API.",
    endpoint_invalid_or_mismatched_completion: "The server returned an unsupported completion or a different model ID. No successful result was recorded.",
    endpoint_response_too_large: "The server response exceeded the 64 KiB limit. Reduce the token limit before reconnecting.",
    endpoint_json_required: "The server must return an application/json response.",
    studio_cannot_be_its_own_model_endpoint: "Use your model server's port, rather than Studio's port.",
    endpoint_disconnected: "The request was discarded because Furnace disconnected.",
    endpoint_evaluation_cancelled_or_budget_exhausted: "Evaluation stopped after disconnect or its 30-second request budget. Missing cases did not pass.",
    add_evaluation_cases_first: "Add and save evaluation cases in the workspace first.",
    managed_server_not_running: "The Furnace-operated server is not running. Start it again; its per-launch key is never saved.",
    choose_a_managed_model_first: "Save a model selection first.",
    prepare_managed_model_first: "Prepare the model first: its pinned image and verified weights are not present yet.",
    stop_managed_server_first: "Stop the managed server before changing its selection.",
    preparation_in_progress: "Preparation is still running. Wait for it or cancel it.",
    managed_cleanup_unconfirmed_stop_first: "Cleanup is unconfirmed. Restore Docker, then stop the managed server before changing or starting it.",
    cleanup_unconfirmed: "Docker could not confirm cleanup. Restore Docker and stop again.",
    studio_shutting_down: "Studio is shutting down. Reopen it before starting new work.",
    managed_server_already_running: "The managed server is already running.",
    server_out_of_memory: "The server ran out of its container memory. Raise the memory limit or lower the context size, then start again.",
    server_load_timeout: "The server did not become ready in time. Check its logs, then start again.",
    server_load_failed: "The server reported that loading failed. Check its logs.",
    image_not_prepared: "The pinned server image is missing. Prepare again.",
    docker_unavailable: "Docker is not reachable. Start Docker Desktop (Linux containers) and try again.",
    docker_operation_failed: "A Docker operation failed. Check that Docker is running and has enough memory and disk.",
    artifact_digest_mismatch: "The stored weights no longer match their pinned SHA-256 and were quarantined. Prepare again.",
    download_digest_mismatch: "The downloaded weights did not match the pinned SHA-256 and were discarded. Prepare again.",
    insufficient_disk_space: "Not enough free disk space for the weights.",
    download_cancelled: "Preparation was cancelled. Prepare again to resume the download.",
    reference_suite_digest_mismatch: "The packaged reference suite does not match its pinned digest; it was not loaded.",
    gpu_runtime_unavailable: "Docker does not offer an NVIDIA GPU runtime here. Choose CPU, or enable GPU support in Docker Desktop (WSL2) with a current NVIDIA driver.",
    memory_exceeds_docker_limit: "The memory limit is larger than Docker can provide. Lower it, or raise the memory available to Docker Desktop.",
    cpus_exceed_docker_limit: "More CPUs were requested than Docker can provide. Lower the CPU setting.",
    linux_containers_required: "Switch Docker Desktop to Linux containers.",
    local_image_not_present: "That local image ID is not present in Docker. Build or load the image first.",
    adapter_image_not_pinned: "Pin the adapter image by digest (name@sha256:…) or use a local image ID (sha256:…).",
    adapter_folder_contains_symlink: "The adapter folder contains a symbolic link. Replace it with real files so the digest matches what runs.",
    adapter_folder_too_large_to_digest: "The adapter code folder is too large to digest (over 5,000 files or 256 MiB). Point it at the code only, and put weights in the weights folder.",
  };
  if (/^server_exited_\d+$/.test(reason)) return "The server process exited (code " + reason.split("_").pop() + "). Check its logs, then start again explicitly.";
  if (/^download_(http_\d{3}|network_error)$/.test(reason)) return "The download failed (" + reason.slice(9) + "). Prepare again to resume.";
  if (/^endpoint_http_\d{3}$/.test(reason)) return "The local server returned HTTP " + reason.slice(-3) + ". Redirects are not followed; upstream error text is withheld. Check your server, then reconnect.";
  return messages[reason] || reason;
}
async function api(path, method = "GET", body) {
  const response = await fetch("/api/" + path, {method, headers: {"X-Furnace-Session": token, ...(body ? {"Content-Type":"application/json"} : {})}, body: body ? JSON.stringify(body) : undefined});
  if (!response.ok) {
    let reason = response.status === 401 ? "Reopen the private session link printed by Studio." : "Request failed; refresh and check the server.";
    try { const data = await response.json(); if (typeof data.detail === "string") reason = data.detail; } catch {}
    throw new Error(readableError(reason));
  }
  return response.headers.get("content-type")?.includes("application/zip") ? response.blob() : response.json();
}
function current() { return projects.find(p => p.id === selected); }
function accept(incoming) {
  const previous = projects.find(p => p.id === incoming.id);
  if (!previous) return;
  const value = mergeProjectRecord(previous, incoming);
  projects = projects.map(p => p.id === value.id ? value : p);
  if (selected === value.id) render();
}
function formData() {
  const value = Object.fromEntries(new FormData($("#connection-form")));
  for (const key of ["timeout_seconds", "max_tokens", "evaluation_budget_seconds"]) value[key] = Number(value[key]);
  return value;
}
function render() {
  const p = current();
  $("#model-workspace").hidden = !p;
  $("#empty-projects").hidden = projects.length > 0;
  if (!p) return;
  const endpoint = p.model_endpoint;
  $("#model-prompt-form").elements.namedItem("input").value = prompts.get(p.id) || "";
  const saved = drafts.get(p.id) || (endpoint.connection?.managed ? null : endpoint.connection) || {timeout_seconds:30, max_tokens:256, evaluation_budget_seconds:120};
  const form = $("#connection-form");
  form.reset();
  for (const [key,value] of Object.entries(saved)) if (form.elements.namedItem(key)) form.elements.namedItem(key).value = value;
  $("#connection-draft").textContent = drafts.has(p.id) ? "Unsaved settings · kept for this project in this tab. Requests use saved settings." : "Saved settings. No connection is inferred from file presence.";
  const ready = endpoint.state.status === "connected" && !refreshing;
  $("#model-state").textContent = refreshing ? "Reconfirming saved state; prior evidence is withheld." : endpoint.state.status + " · " + (endpoint.state.reason || "Not connected");
  for (const button of document.querySelectorAll("#model-workspace button")) button.disabled = busy || refreshing;
  $("#model-connect").disabled = busy || refreshing || !endpoint.connection;
  $("#model-disconnect").disabled = !endpoint.connection;
  renderManaged(p);
  $("#model-prompt-form button").disabled ||= !ready;
  $("#model-evaluate").disabled ||= !ready || !p.cases.length;
  const record = outputs.get(p.id);
  $("#model-output").textContent = record && !refreshing
    ? requestOutputFor({id:p.id,configuration_sha256:endpoint.configuration_sha256}, record)
    : "No confirmed endpoint response in this tab.";
  const run = !refreshing && endpoint.verification === "current_endpoint_observation" ? endpoint.evaluation : null;
  $("#model-run").textContent = run
    ? "Saved endpoint attempt: " + run.status + " · " + new Date(run.at).toLocaleString() + (run.elapsed_seconds !== undefined ? " · " + run.elapsed_seconds + " s" : "") + ". Reopening does not rerun it. " + (endpoint.weights_verified_before_launch ? "Weights SHA-256 verified before launch." : "Model identity not independently verified.")
    : "No endpoint evidence for this current project/configuration.";
  const repro = run ? endpoint.reproducibility : null;
  $("#model-repro").textContent = !repro ? "" : repro.status === "no_earlier_run"
    ? "Reproducibility: no earlier completed attempt with this configuration to compare."
    : "Reproducibility: " + repro.identical + " of " + repro.compared + " outputs identical to attempt " + repro.reference_run_id.slice(0, 8) + (repro.reference_launch_id && repro.reference_launch_id !== repro.current_launch_id ? " (an earlier server launch)" : "") + ".";
  const list = $("#model-results"); list.replaceChildren();
  for (const [index,item] of p.cases.entries()) {
    const result = run?.results?.find(r => r.case_index === index);
    const row = document.createElement("p");
    const rule = result?.scoring_method && result.scoring_method !== "none" ? " · " + result.scoring_method + " rule" : "";
    row.textContent = item.name + " — " + (result?.status || "not_run") + rule + (result?.duration_ms !== undefined ? " · HTTP round trip " + result.duration_ms + " ms (not TTFT)" : "") + (result?.reason ? " · " + result.reason : "");
    list.append(row);
  }
  const history = refreshing ? [] : endpoint.history || [];
  $("#model-history-state").textContent = refreshing
    ? "Reconfirming saved history…"
    : history.length + " retained attempts (limit " + endpoint.history_limit + "). Newest first; opening an attempt sends no request.";
  const archive = $("#model-history");
  const historyIdentity = JSON.stringify([p.id, history]);
  // Preserve native disclosure state and keyboard focus during unrelated updates.
  if (archive.dataset.historyIdentity === historyIdentity) return;
  archive.dataset.historyIdentity = historyIdentity;
  archive.replaceChildren();
  for (const attempt of history.slice().reverse()) {
    const entry = document.createElement("details"), heading = document.createElement("summary");
    const binding = attempt.matches_current_configuration ? "Current saved configuration" : "Earlier or unbound configuration";
    heading.textContent = new Date(attempt.at).toLocaleString() + " · " + attempt.status + " · " + binding;
    const identification = document.createElement("p");
    identification.textContent = "Attempt " + attempt.run_id + " · Model ID: " + (attempt.model_id || "not recorded") + " · Declared revision: " + (attempt.declared_revision || "not recorded");
    const counts = document.createElement("p");
    const results = attempt.results || [];
    counts.textContent = ["exact_pass", "exact_fail", "check_pass", "check_fail", "unscored", "incomplete", "error"].map(status => status + ": " + results.filter(r => r.status === status).length).join(" · ")
      + (Number.isInteger(attempt.case_count) ? " · not_run: " + Math.max(0, attempt.case_count - results.length) : " · original case count not recorded");
    const record = document.createElement("pre"); record.className = "guide-code";
    record.textContent = JSON.stringify(attempt, null, 2);
    entry.append(heading, identification, counts, record); archive.append(entry);
  }
}
async function refresh() {
  const generation = ++refreshGeneration;
  notice("");
  $("#model-consent").checked = false;
  refreshing = true; render();
  try {
    const saved = await api("projects");
    if (generation !== refreshGeneration) return;
    projects = saved.map(p => mergeProjectRecord(projects.find(old => old.id === p.id), p));
    if (!projects.some(p => p.id === selected)) selected = projects[0]?.id || null;
    const selector = $("#model-project"); selector.replaceChildren();
    for (const p of projects) { const option = document.createElement("option"); option.value = p.id; option.textContent = p.name; selector.append(option); }
    selector.value = selected || "";
    refreshing = false; render();
  } catch (error) {
    if (generation !== refreshGeneration) return;
    notice("Saved state not confirmed: " + error.message); render();
  }
}
async function action(fn) {
  if (busy || !current()) return;
  const pid = selected;
  busy = true; notice("Working with the saved local endpoint settings…"); render();
  try { await fn(pid); notice("Request completed. Inspect its status and limitations below."); }
  catch (error) { notice(error.message); }
  finally { busy = false; try { accept(await api("projects/" + pid + "/model")); } catch {} render(); }
}
$("#model-project").onchange = event => {
  selected = event.target.value; $("#model-consent").checked = false; notice(""); render();
};
$("#connection-form").oninput = () => {
  if (selected) { drafts.set(selected, formData()); $("#connection-draft").textContent = "Unsaved settings · kept for this project in this tab."; }
};
$("#connection-form").onsubmit = event => {
  event.preventDefault(); const value = formData();
  action(async pid => { const p = await api("projects/" + pid + "/model/connection", "PUT", value); drafts.delete(pid); accept(p); $("#model-consent").checked = false; });
};
$("#model-connect").onclick = () => action(async pid => accept(await api("projects/" + pid + "/model/connect", "POST", {consent:$("#model-consent").checked})));
$("#model-disconnect").onclick = async () => {
  const pid = selected;
  try { accept(await api("projects/" + pid + "/model/disconnect", "POST")); notice("Disconnected; Furnace did not stop the external server."); }
  catch (error) { notice(error.message); }
};
$("#model-prompt-form").onsubmit = event => {
  event.preventDefault(); const value = new FormData(event.target).get("input");
  action(async pid => {
    const result = await api("projects/" + pid + "/model/predict", "POST", {input:value});
    outputs.set(pid, {...result, text:result.output + "\n\nHTTP round trip " + result.duration_ms + " ms · finish: " + result.finish_reason + "\nServer model: " + result.model_id + " (not independently verified). Not TTFT or semantic quality."});
  });
};
$("#model-prompt-form").oninput = event => { if (selected) prompts.set(selected, new FormData(event.currentTarget).get("input")); };
$("#model-evaluate").onclick = () => action(async pid => accept(await api("projects/" + pid + "/model/evaluate", "POST")));
$("#model-export").onclick = () => action(async pid => {
  const blob = await api("projects/" + pid + "/kit", "POST");
  const url = URL.createObjectURL(blob), link = document.createElement("a");
  link.href = url; link.download = "furnace-starter-kit.zip"; link.click(); URL.revokeObjectURL(url);
});

function describeRecipe(id) {
  if (id === "python-adapter") return "Your own Python adapter: " + (catalog?.custom_adapter?.requires || "") + " Weights: " + (catalog?.custom_adapter?.weights_verification || "") + ".";
  const recipe = catalog?.models.find(m => m.id === id);
  if (!recipe) return "Choose a reviewed recipe. Every input that decides what runs is pinned.";
  const local = recipe.local?.state === "present" ? "weights already verified locally" : recipe.local?.state === "partial" ? "partial download present (resumes)" : (recipe.download_bytes / 1048576).toFixed(0) + " MiB to download";
  return recipe.name + " · " + recipe.architecture + " · " + recipe.parameters + " parameters · license " + recipe.license + " · " + recipe.repository + "@" + recipe.revision.slice(0, 12) + " · weights sha256 " + recipe.weights.sha256.slice(0, 12) + "… · " + local + ". " + recipe.hardware;
}
function renderManaged(p) {
  const managed = p.managed_server || {status: "not_configured"};
  const form = $("#managed-form");
  const selection = drafts.get(p.id + ":managed") || managed.selection;
  if (selection) for (const [key, value] of Object.entries(selection)) if (key !== "python" && form.elements.namedItem(key)) form.elements.namedItem(key).value = value;
  for (const [key, value] of Object.entries(selection?.python || {})) if (form.elements.namedItem("python_" + key)) form.elements.namedItem("python_" + key).value = value ?? "";
  $("#custom-adapter").hidden = form.elements.namedItem("model").value !== "python-adapter";
  $("#managed-recipe").textContent = describeRecipe(form.elements.namedItem("model").value);
  const status = managed.status;
  const job = managed.preparation;
  let text = {
    not_configured: "No managed model selected for this project.",
    configured: "Selection saved. Prepare to download and verify; nothing has run.",
    preparing: "Preparing…",
    prepared: "Prepared: images pulled by digest and weights SHA-256 verified. Start when ready.",
    starting: "Starting the isolated container…",
    loading: "Loading model weights…",
    ready: "Ready" + (managed.start_seconds ? " in " + managed.start_seconds + " s" : "") + " · connected for evaluation below.",
    stopped: "Stopped. Start again explicitly.",
    interrupted: "The previous Studio session ended; its container was removed. Start again explicitly.",
    failed: "Failed: " + readableError(managed.reason || "unknown"),
    unknown: "Cleanup could not be confirmed: " + (managed.reason || "") + ". Check Docker, then stop again.",
  }[status] || status;
  if (job?.phase === "image") text = "Pulling pinned image " + job.image.split("@")[0] + "…";
  if (job?.phase === "weights") text = "Downloading and verifying " + job.file + "…";
  if (managed.manifest_sha256 && ["prepared", "ready", "stopped"].includes(status)) text += " Manifest " + managed.manifest_sha256.slice(0, 12) + ".";
  $("#managed-status").textContent = text;
  const progress = $("#managed-progress");
  progress.hidden = !(job?.phase === "weights" && job.size);
  if (!progress.hidden) progress.value = job.bytes / job.size;
  const active = ["starting", "loading", "ready", "unknown"].includes(status);
  const consent = $("#managed-consent").checked;
  $("#managed-save").disabled = busy || active || status === "preparing";
  $("#managed-prepare").disabled = busy || !managed.selection || active || status === "preparing" || !consent;
  $("#managed-cancel").disabled = status !== "preparing";
  $("#managed-start").disabled = busy || !managed.selection || active || status === "preparing" || !consent;
  $("#managed-stop").disabled = !active && status !== "unknown" && status !== "failed";
  $("#managed-suite").disabled = busy || !managed.selection || active;
  const gpu = catalog?.docker?.gpu_runtime;
  form.elements.namedItem("accelerator").querySelector("option[value=nvidia]").disabled = gpu === false;
  if (status === "preparing" && !managedPoll) managedPoll = setTimeout(pollManaged, 1000);
}
async function pollManaged() {
  managedPoll = null;
  const pid = selected;
  if (!pid) return;
  try {
    const view = await api("projects/" + pid + "/managed");
    const p = projects.find(item => item.id === pid);
    if (p) { p.managed_server = view; if (selected === pid) render(); }
    if (view.status !== "preparing") accept(await api("projects/" + pid + "/model"));
  } catch (error) { notice(error.message); }
}
function managedSelection() {
  const value = Object.fromEntries(new FormData($("#managed-form")));
  const python = {};
  for (const key of Object.keys(value)) if (key.startsWith("python_")) { python[key.slice(7)] = value[key]; delete value[key]; }
  if (value.model === "python-adapter") value.python = {...python, weights_path: python.weights_path || null};
  for (const key of ["threads", "memory_mb", "context_tokens", "request_timeout_seconds", "max_tokens", "evaluation_budget_seconds"]) value[key] = Number(value[key]);
  return value;
}
async function loadCatalog() {
  try {
    catalog = await api("managed/catalog");
    const select = $("#managed-model"); select.replaceChildren();
    for (const recipe of catalog.models) { const option = document.createElement("option"); option.value = recipe.id; option.textContent = recipe.name; select.append(option); }
    const custom = document.createElement("option"); custom.value = "python-adapter"; custom.textContent = "Your own Python adapter (advanced)"; select.append(custom);
    render();
  } catch (error) { $("#managed-recipe").textContent = "Recipes unavailable: " + error.message; }
}
$("#managed-form").oninput = () => { if (selected) { drafts.set(selected + ":managed", managedSelection()); $("#managed-recipe").textContent = describeRecipe($("#managed-model").value); $("#custom-adapter").hidden = $("#managed-model").value !== "python-adapter"; } };
$("#managed-form").onsubmit = event => { event.preventDefault(); const value = managedSelection(); action(async pid => { const saved = await api("projects/" + pid + "/managed", "PUT", value); drafts.delete(pid + ":managed"); accept(saved); }); };
$("#managed-consent").onchange = () => render();
$("#managed-prepare").onclick = () => action(async pid => { const view = await api("projects/" + pid + "/managed/prepare", "POST", {consent: true}); const p = current(); if (p) p.managed_server = view; });
$("#managed-cancel").onclick = async () => { try { await api("projects/" + selected + "/managed/cancel", "POST"); notice("Cancelling; the partial download is kept and resumes next time."); } catch (error) { notice(error.message); } };
$("#managed-start").onclick = () => action(async pid => { notice("Starting the server and waiting for it to report ready. Loading can take a minute."); await api("projects/" + pid + "/managed/start", "POST", {consent: true}); });
$("#managed-stop").onclick = async () => { const pid = selected; try { await api("projects/" + pid + "/managed/stop", "POST"); accept(await api("projects/" + pid + "/model")); notice("Managed server stopped and its container removed."); } catch (error) { notice(error.message); } };
$("#managed-suite").onclick = () => action(async pid => accept(await api("projects/" + pid + "/managed/suite", "POST")));
$("#managed-observe-refresh").onclick = async () => {
  const out = $("#managed-observe");
  try {
    const data = await api("projects/" + selected + "/managed/observe");
    const lines = ["Status: " + data.managed_server.status];
    if (data.container) lines.push("Container " + data.container.container_id + " · running " + data.container.running + " · networks " + data.container.networks.join(", "));
    if (data.gpu?.name) lines.push("GPU: " + data.gpu.name + " · memory " + data.gpu.memory_used_mib + "/" + data.gpu.memory_total_mib + " MiB · utilization " + data.gpu.utilization_percent + "% · " + data.gpu.temperature_c + " °C");
    if (data.resources?.memory) lines.push("Resources: CPU " + data.resources.cpu_percent + " · memory " + data.resources.memory + " · processes " + data.resources.pids);
    const metrics = Object.entries(data.metrics || {}).filter(([k]) => /tokens|requests/.test(k)).map(([k, v]) => k.replace("llamacpp:", "") + "=" + v);
    if (metrics.length) lines.push("Server metrics: " + metrics.join(" · "));
    lines.push("", "Recent operations (no prompts or outputs):", ...data.operations.slice(-12).map(e => e.at.slice(11, 19) + " " + e.kind + (e.duration_ms !== undefined ? " " + e.duration_ms + " ms" : "") + (e.reason ? " " + e.reason : "")));
    if (data.logs) lines.push("", "Server log tail:", data.logs.split("\n").slice(-25).join("\n"));
    out.textContent = lines.join("\n"); out.hidden = false;
  } catch (error) { out.textContent = error.message; out.hidden = false; }
};
$("#model-refresh").onclick = refresh;
window.addEventListener("pageshow", event => { if (event.persisted) { $("#model-consent").checked = false; refresh(); } });
window.addEventListener("beforeunload", event => { if (drafts.size) { event.preventDefault(); event.returnValue = ""; } });
refresh();
loadCatalog();
