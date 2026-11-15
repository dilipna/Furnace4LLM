import {mergeProjectRecord, requestOutputFor} from "./studio-state.mjs";
const $ = selector => document.querySelector(selector);
const fragment = new URLSearchParams(location.hash.slice(1)).get("session");
const token = fragment || sessionStorage.getItem("furnace-session") || "";
if (fragment) { sessionStorage.setItem("furnace-session", fragment); history.replaceState(null, "", "/model"); }
let projects = [], selected = null, busy = false, refreshing = false;
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
  };
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
  value.timeout_seconds = Number(value.timeout_seconds); value.max_tokens = Number(value.max_tokens);
  return value;
}
function render() {
  const p = current();
  $("#model-workspace").hidden = !p;
  $("#empty-projects").hidden = projects.length > 0;
  if (!p) return;
  const endpoint = p.model_endpoint;
  $("#model-prompt-form").elements.namedItem("input").value = prompts.get(p.id) || "";
  const saved = drafts.get(p.id) || endpoint.connection || {timeout_seconds:5, max_tokens:128};
  const form = $("#connection-form");
  form.reset();
  for (const [key,value] of Object.entries(saved)) if (form.elements.namedItem(key)) form.elements.namedItem(key).value = value;
  $("#connection-draft").textContent = drafts.has(p.id) ? "Unsaved settings · kept for this project in this tab. Requests use saved settings." : "Saved settings. No connection is inferred from file presence.";
  const ready = endpoint.state.status === "connected" && !refreshing;
  $("#model-state").textContent = refreshing ? "Reconfirming saved state; prior evidence is withheld." : endpoint.state.status + " · " + (endpoint.state.reason || "Not connected");
  for (const button of document.querySelectorAll("#model-workspace button")) button.disabled = busy || refreshing;
  $("#model-connect").disabled = busy || refreshing || !endpoint.connection;
  $("#model-disconnect").disabled = !endpoint.connection;
  $("#model-prompt-form button").disabled ||= !ready;
  $("#model-evaluate").disabled ||= !ready || !p.cases.length;
  const record = outputs.get(p.id);
  $("#model-output").textContent = record && !refreshing
    ? requestOutputFor({id:p.id,configuration_sha256:endpoint.configuration_sha256}, record)
    : "No confirmed endpoint response in this tab.";
  const run = !refreshing && endpoint.verification === "current_endpoint_observation" ? endpoint.evaluation : null;
  $("#model-run").textContent = run
    ? "Saved endpoint attempt: " + run.status + " · " + new Date(run.at).toLocaleString() + ". Reopening does not rerun it. Model identity not independently verified."
    : "No endpoint evidence for this current project/configuration.";
  const list = $("#model-results"); list.replaceChildren();
  for (const [index,item] of p.cases.entries()) {
    const result = run?.results?.find(r => r.case_index === index);
    const row = document.createElement("p");
    row.textContent = item.name + " — " + (result?.status || "not_run") + (result?.duration_ms !== undefined ? " · HTTP round trip " + result.duration_ms + " ms (not TTFT)" : "") + (result?.reason ? " · " + result.reason : "");
    list.append(row);
  }
}
async function refresh() {
  $("#model-consent").checked = false;
  refreshing = true; render();
  try {
    const saved = await api("projects");
    projects = saved.map(p => mergeProjectRecord(projects.find(old => old.id === p.id), p));
    if (!projects.some(p => p.id === selected)) selected = projects[0]?.id || null;
    const selector = $("#model-project"); selector.replaceChildren();
    for (const p of projects) { const option = document.createElement("option"); option.value = p.id; option.textContent = p.name; selector.append(option); }
    selector.value = selected || "";
    refreshing = false; render();
  } catch (error) { notice("Saved state not confirmed: " + error.message); render(); }
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
$("#model-refresh").onclick = refresh;
window.addEventListener("pageshow", event => { if (event.persisted) { $("#model-consent").checked = false; refresh(); } });
window.addEventListener("beforeunload", event => { if (drafts.size) { event.preventDefault(); event.returnValue = ""; } });
refresh();
