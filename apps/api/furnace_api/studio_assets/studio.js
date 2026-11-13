import {activeStates, caseStatus, countsFor, journeyFor, runtimeState, toneFor} from "./studio-state.mjs";

const $ = selector => document.querySelector(selector);
const token = new URLSearchParams(location.hash.slice(1)).get("session") || sessionStorage.getItem("furnace-session");
if (token) {
  sessionStorage.setItem("furnace-session", token);
  history.replaceState(null, "", location.pathname);
}
window.addEventListener("hashchange", () => {
  if (new URLSearchParams(location.hash.slice(1)).has("session")) location.reload();
});

let projects = [], current = null, view = "overview", polling = false, renderedProjectId = null;
const pending = new Set(), drafts = new Map(), baselines = new Map(), outputs = new Map(), checked = new Map();
const formNames = {"contract-form": "contract", "plan-form": "plan", "case-form": "case", "predict-form": "predict"};
const formKey = (id, name) => `${id}:${name}`;
const isPending = (kind, id = current?.id) => pending.has(formKey(id, kind));
const defaultOutput = "No request yet. Start a worker, then send a sanitized input.";
const casePayload = c => ({name: c.name, input: c.input, expected_behavior: c.expected_behavior, expected_output: c.expected_output ?? null});

function text(tag, content, className) {
  const element = document.createElement(tag);
  element.textContent = content;
  if (className) element.className = className;
  return element;
}
function notice(message, tone = "error") {
  $("#notice").textContent = message;
  $("#notice").dataset.tone = tone;
}
async function api(path, method = "GET", data) {
  let response;
  try {
    response = await fetch("/api/" + path, {
      method,
      headers: {"X-Furnace-Session": token || "", ...(data ? {"Content-Type": "application/json"} : {})},
      body: data ? JSON.stringify(data) : undefined,
    });
  } catch { throw new Error("Studio could not be reached. Keep its application terminal open, then retry."); }
  if (!response.ok) {
    let message = "Check the form values and retry.";
    try { const body = await response.json(); if (typeof body.detail === "string") message = body.detail; }
    catch { message = response.status === 401 ? "Session unavailable. Reopen the new private session link printed by furnace studio." : "Workspace request failed. Check the application terminal."; }
    throw new Error(message);
  }
  if (response.status === 204) return null;
  return response.headers.get("content-type")?.includes("application/zip") ? response.blob() : response.json();
}
async function action(button, kind, fn, id = current?.id) {
  const key = formKey(id, kind);
  if (pending.has(key)) return;
  pending.add(key);
  const original = button.textContent;
  const busyLabels = {start: "Starting worker…", stop: "Stopping worker…", predict: "Running request…", evaluate: "Running checks…", prepare: "Preparing image…", environment: "Checking environment…", download: "Preparing download…", refresh: "Refreshing…", example: "Opening example…", "add-project": "Inspecting project…"};
  button.textContent = busyLabels[kind] || "Saving…";
  button.setAttribute("aria-busy", "true");
  button.disabled = true;
  notice("");
  syncControls();
  try { await fn(id); }
  catch (error) { notice(error.message); }
  finally {
    pending.delete(key);
    button.removeAttribute("aria-busy");
    button.textContent = original;
    button.disabled = false;
    syncControls();
  }
}
function acceptProject(project) {
  if (projects.some(item => item.id === project.id)) projects = projects.map(item => item.id === project.id ? project : item);
  else projects.push(project);
  if (current?.id === project.id) { current = project; render(); }
  else navigation();
}
async function refreshProject(id = current?.id) {
  if (!id) return;
  const project = await api("projects/" + id);
  checked.set(id, new Date());
  acceptProject(project);
}
function openProject(project) {
  current = project; view = "overview"; notice(""); render();
}
function navigation() {
  $("#count").textContent = projects.length + " / 2";
  $("#projects").replaceChildren(...projects.map(project => {
    const button = text("button", project.name, "project-button");
    button.dataset.project = project.id;
    button.append(text("small", project.origin === "guided_example" ? "Guided example · " + runtimeState(project).status.replaceAll("_", " ") : "Model not connected · local project"));
    if (current?.id === project.id) button.setAttribute("aria-current", "true");
    button.onclick = () => openProject(project);
    return button;
  }));
  $("#new-project").disabled = projects.length >= 2;
  $("#new-project").title = projects.length >= 2 ? "Two project slots are in use. Remove a workspace record in Activity to add another." : "Inspect a local model folder";
  $("#open-example").disabled = isPending("example", null) || (projects.length >= 2 && !projects.some(p => p.origin === "guided_example"));
}
function changeView(next, focus = false) {
  view = next; renderPanels();
  if (focus) {
    const heading = document.querySelector(`[data-panel="${view}"] h2`);
    if (heading) { heading.tabIndex = -1; heading.focus({preventScroll: true}); }
  }
}
function renderPanels() {
  document.querySelectorAll("[data-panel]").forEach(panel => panel.hidden = panel.dataset.panel !== view);
  document.querySelectorAll("[data-view]").forEach(button => {
    if (button.dataset.view === view) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  const environment = $("#environment");
  if (current && view === "infrastructure") $("#environment-anchor").append(environment);
  else $("#main").insertBefore(environment, $("footer"));
}
function readForm(form) {
  const data = {};
  for (const field of form.elements) {
    if (!field.name || ["submit", "button"].includes(field.type)) continue;
    if (field.type === "radio") { if (field.checked) data[field.name] = field.value; }
    else data[field.name] = field.type === "checkbox" ? field.checked : field.value;
  }
  return data;
}
function populateForm(form, values) {
  form.reset();
  for (const [key, value] of Object.entries(values)) {
    const field = form.elements.namedItem(key);
    if (!field) continue;
    if (field.type === "checkbox") field.checked = Boolean(value);
    else field.value = value ?? "";
  }
}
function renderForm(name, saved) {
  const form = $("#" + Object.keys(formNames).find(key => formNames[key] === name));
  const key = formKey(current.id, name);
  populateForm(form, drafts.get(key) || saved);
  if (!drafts.has(key)) baselines.set(key, JSON.stringify(readForm(form)));
}
function draftLabels() {
  for (const name of ["contract", "plan", "case"]) $("#" + name + "-draft").textContent = current && drafts.has(formKey(current.id, name)) ? "Unsaved draft · kept in this tab" : "";
}
for (const [formId, name] of Object.entries(formNames)) {
  const capture = () => {
    if (!current) return;
    const data = readForm($("#" + formId)), key = formKey(current.id, name);
    if (JSON.stringify(data) === baselines.get(key)) drafts.delete(key);
    else drafts.set(key, data);
    draftLabels();
    $("#exact-output-label").hidden = !$("#case-form").elements.namedItem("expect_exact").checked;
  };
  $("#" + formId).addEventListener("input", capture);
  $("#" + formId).addEventListener("change", capture);
}
window.addEventListener("beforeunload", event => {
  if ([...drafts.keys()].some(key => !key.endsWith(":predict"))) { event.preventDefault(); event.returnValue = ""; }
});
function syncEntryControls() {
  $("#project-limit").hidden = projects.length < 2;
  $("#open-example").disabled = isPending("example", null) || (projects.length >= 2 && !projects.some(p => p.origin === "guided_example"));
  $("#check-environment").disabled = isPending("environment", null);
}
function syncControls() {
  syncEntryControls();
  if (!current) return;
  const state = runtimeState(current), active = activeStates.includes(state.status);
  for (const [formId, name] of Object.entries(formNames)) {
    const form = $("#" + formId);
    const disabled = name === "predict" ? state.status !== "ready" || isPending("predict") : active || isPending("save-" + name);
    for (const field of form.elements) field.disabled = disabled;
  }
  $("#evaluate").disabled = state.status !== "ready" || !current.cases.length || isPending("evaluate");
  $("#start").disabled = ["ready", "starting", "unknown"].includes(state.status) || isPending("start") || isPending("stop");
  $("#stop-runtime").disabled = ["not_connected", "stopped", "interrupted"].includes(state.status) || isPending("stop");
  $("#prepare-runtime").disabled = isPending("prepare", null);
  $("#download").disabled = isPending("download");
  $("#refresh-runtime").disabled = isPending("refresh");
  $("#adapter").disabled = active;
  $("#runtime-consent").disabled = active;
  document.querySelectorAll("[data-remove-case]").forEach(button => button.disabled = active || isPending("save-case"));
}
function renderJourney() {
  const journey = journeyFor(current);
  $("#next-title").textContent = journey.next.title;
  $("#next-description").textContent = journey.next.description;
  $("#next-action").textContent = journey.next.action;
  $("#progress").replaceChildren(...journey.stages.map((step, index) => {
    const li = text("li", ""); li.dataset.complete = step.done;
    const button = text("button", ""); button.append(text("span", step.done ? "✓" : index + 1), text("strong", step.label));
    button.setAttribute("aria-label", step.label + (step.done ? ": prepared or executed" : ": incomplete"));
    button.onclick = () => changeView(step.view, true); li.append(button); return li;
  }));
  const metrics = [
    [Object.values(current.assessment.file_evidence).filter(Boolean).length + " / 5", "File signals detected"],
    [String(current.cases.length), "Prepared evaluation cases"],
    [current.evaluation?.status?.replaceAll("_", " ") || "Not run", "Framework execution"],
  ];
  $("#project-metrics").replaceChildren(...metrics.map(([value, label]) => { const div = text("div", "", "metric"); div.append(text("strong", value), text("span", label)); return div; }));
}
function renderEvaluation() {
  const evaluation = current.evaluation, counts = countsFor(current);
  $("#evaluation-summary").textContent = evaluation
    ? `Attempt ${evaluation.status}. Configuration ${evaluation.configuration_sha256?.slice(0,12) || "unavailable"}. Fixture evidence only; no model-quality claim.`
    : "No run yet. Start the local fixture, then execute your cases. Descriptive expectations alone are not scored.";
  const labels = {framework_pass: "Exact checks passed", framework_fail: "Exact checks failed", unscored: "Unscored", error: "Execution errors", not_run: "Not run"};
  $("#evaluation-results").replaceChildren(...Object.entries(labels).map(([status, label]) => {
    const item = text("div", "", "result-stat"); item.append(text("strong", counts[status]), text("span", label)); return item;
  }));
  $("#cases").replaceChildren(...current.cases.map((item, index) => {
    const card = text("article", "", "case"), status = caseStatus(current, index);
    const badge = text("span", status.replaceAll("_", " ").toUpperCase(), "state"); badge.dataset.tone = toneFor(status);
    card.append(badge, text("h3", item.name), text("p", "Input: " + item.input), text("p", "Expected behavior: " + item.expected_behavior), text("p", item.expected_output == null ? "Scoring: no exact assertion — an executed case remains unscored." : "Exact output: " + item.expected_output));
    const evidence = evaluation?.results?.find(result => result.case_index === index);
    const footer = text("div", "", "case-footer");
    footer.append(text("span", evidence?.request_id ? `Request ${evidence.request_id} · ${evidence.duration_ms} ms` : evidence?.reason ? `Execution note: ${evidence.reason.replaceAll("_", " ")}` : "No execution evidence for this case."));
    const remove = text("button", "Remove case", "text-button"); remove.dataset.removeCase = index;
    const id = current.id, cases = current.cases.map(casePayload);
    remove.onclick = () => action(remove, "save-case", async () => acceptProject(await api(`projects/${id}/cases`, "PUT", {cases: cases.filter((_, i) => i !== index)})), id);
    footer.append(remove); card.append(footer); return card;
  }));
  if (!current.cases.length) $("#cases").append(text("p", "No cases yet. Add a representative input below; it stays Not run until execution."));
  if (!current.cases.length || drafts.has(formKey(current.id, "case"))) $("#add-case-details").open = true;
}
function render() {
  const previousFocus = document.activeElement;
  const projectFocus = previousFocus?.dataset?.project;
  navigation();
  $("#welcome").hidden = Boolean(current); $("#workspace").hidden = !current;
  if (!current) { renderedProjectId = null; renderPanels(); syncEntryControls(); return; }
  if (renderedProjectId !== current.id) $("#runtime-consent").checked = false;
  renderedProjectId = current.id;
  $("#project-title").textContent = current.name;
  $("#project-path").textContent = current.origin === "guided_example" ? "Bundled metadata example · no source or weights are executed" : current.path;
  $("#example-note").hidden = current.origin !== "guided_example";
  $("#project-kind").textContent = current.origin === "guided_example" ? "GUIDED INFRASTRUCTURE WALKTHROUGH" : "RESEARCHER WORKSPACE";
  const labels = {configuration_file_present: "Configuration", checkpoint_file_present: "Checkpoints", python_source_present: "Python source", dependency_manifest_present: "Dependencies", test_files_present: "Tests"};
  $("#evidence").replaceChildren(...Object.entries(current.assessment.file_evidence).map(([key, value]) => text("span", labels[key] + (value ? " · detected" : " · not detected"), "chip" + (value ? "" : " missing"))));
  const titles = {model_loading: "Model loading", serving_and_harness: "Serving & harness", security: "Security boundaries", evaluations: "Evaluations", logs_and_metrics: "Logs & metrics", operations: "Operations & recovery"};
  $("#capabilities").replaceChildren(...current.assessment.capabilities.map(capability => { const card = text("article", "", "capability"); card.append(text("span", "REQUIRES VALIDATION", "state"), text("h3", titles[capability.area] || capability.area), text("p", capability.next_action)); return card; }));
  $("#warnings").hidden = !current.assessment.warnings.length; $("#warnings").textContent = current.assessment.warnings.join(" · ");
  renderForm("contract", current.contract); renderForm("plan", current.plan || {}); renderForm("case", {}); renderForm("predict", {});
  draftLabels(); $("#exact-output-label").hidden = !$("#case-form").elements.namedItem("expect_exact").checked;
  const state = runtimeState(current);
  $("#project-state").textContent = state.status === "not_connected" ? "MODEL NOT CONNECTED" : "FIXTURE · " + state.status.replaceAll("_", " ").toUpperCase();
  $("#project-state").dataset.tone = toneFor(state.status);
  $("#runtime-message").textContent = state.reason || state.status;
  $("#runtime-detail").textContent = (checked.has(current.id) ? "Checked " + checked.get(current.id).toLocaleTimeString() + " · " : "") + "Model execution: no · " + (state.container_id ? "Worker " + state.container_id.slice(0,12) : "No confirmed running worker");
  if (state.adapter) $("#adapter").value = state.adapter;
  else $("#adapter").value = "";
  $("#prediction-output").textContent = outputs.get(current.id) || defaultOutput;
  renderJourney(); renderEvaluation();
  $("#events").replaceChildren(...[...current.events].reverse().map(event => { const li = text("li", event.message), time = text("time", new Date(event.at).toLocaleString()); time.dateTime = event.at; li.prepend(time); return li; }));
  $("#remove-confirm").hidden = true; renderPanels(); syncControls();
  if (projectFocus) document.querySelector(`[data-project="${projectFocus}"]`)?.focus({preventScroll: true});
}

$(".brand").onclick = event => {
  if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
  event.preventDefault(); current = null; notice(""); render(); $("#welcome h1").tabIndex = -1; $("#welcome h1").focus();
};
$("#new-project").onclick = () => { current = null; notice(""); render(); $("#add-form input").focus(); };
$("#sections").onclick = event => { const button = event.target.closest("[data-view]"); if (button) changeView(button.dataset.view); };
$("#add-form").onsubmit = event => {
  event.preventDefault(); const form = event.currentTarget, data = readForm(form);
  action(form.querySelector("button"), "add-project", async () => { const project = await api("projects", "POST", data); projects = await api("projects"); form.reset(); openProject(project); $("#project-title").tabIndex = -1; $("#project-title").focus(); }, null);
};
$("#open-example").onclick = event => action(event.currentTarget, "example", async () => {
  const project = await api("examples/framework", "POST");
  if (!projects.some(p => p.id === project.id)) projects.push(project);
  openProject(project); $("#project-title").tabIndex = -1; $("#project-title").focus();
  notice("Guided example opened. Nothing has executed. Review your next step below.", "success");
}, null);
for (const name of ["contract", "plan", "case"]) {
  const form = $("#" + Object.keys(formNames).find(key => formNames[key] === name));
  form.onsubmit = event => {
    event.preventDefault(); const id = current.id, data = readForm(form), cases = current.cases.map(casePayload);
    if (name === "plan") for (const key of ["memory_gb", "timeout_seconds", "log_retention_days"]) data[key] = Number(data[key]);
    if (name === "case") { data.expected_output = data.expect_exact ? data.expected_output : null; delete data.expect_exact; }
    action(form.querySelector("button"), "save-" + name, async () => {
      const project = await api(`projects/${id}/${name === "case" ? "cases" : name}`, "PUT", name === "case" ? {cases: [...cases, data]} : data);
      drafts.delete(formKey(id, name)); acceptProject(project); notice(`Saved “${project.name}” locally. No model execution or cloud provisioning occurred.`, "success");
    }, id);
  };
}
async function downloadKit(id) {
  const blob = await api(`projects/${id}/kit`, "POST"), url = URL.createObjectURL(blob), link = document.createElement("a");
  link.href = url; link.download = "furnace-starter-kit.zip"; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  notice("Starter kit downloaded with the saved assessment, preferences and any framework results. No server was provisioned.", "success");
}
$("#download").onclick = event => action(event.currentTarget, "download", downloadKit);
$("#next-action").onclick = event => {
  if (!current) return;
  const next = journeyFor(current).next;
  if (next.download) return action(event.currentTarget, "download", downloadKit);
  changeView(next.view, true);
  if (next.view === "infrastructure") showEnvironment();
};
$("#prepare-runtime").onclick = event => action(event.currentTarget, "prepare", async () => {
  notice("Preparing the local test image. A first build may take several minutes; keep Studio open.", "success");
  await api("runtime/prepare", "POST"); await checkEnvironment(); notice("Local framework environment prepared. No model was downloaded or run.", "success");
}, null);
$("#start").onclick = event => {
  const id = current.id, adapter = $("#adapter").value, consent = $("#runtime-consent").checked;
  action(event.currentTarget, "start", async () => {
    if (!adapter || !consent) throw new Error("Select the infrastructure fixture and approve local Docker execution first.");
    if (!current.plan) throw new Error("Save infrastructure preferences before starting a worker.");
    const project = projects.find(p => p.id === id);
    acceptProject({...project, runtime: {status: "starting", adapter, reason: "Starting the local infrastructure fixture…", model_execution: false}});
    try { acceptProject(await api(`projects/${id}/start`, "POST", {adapter, consent: true})); }
    finally { await refreshProject(id); }
  }, id);
};
$("#stop-runtime").onclick = event => action(event.currentTarget, "stop", async id => { try { acceptProject(await api(`projects/${id}/stop`, "POST")); } finally { await refreshProject(id); } });
$("#refresh-runtime").onclick = event => action(event.currentTarget, "refresh", refreshProject);
$("#predict-form").onsubmit = event => {
  event.preventDefault(); const form = event.currentTarget, data = readForm(form), id = current.id;
  action(form.querySelector("button"), "predict", async () => {
    outputs.set(id, "Framework request running…"); if (current?.id === id) $("#prediction-output").textContent = outputs.get(id);
    try { const result = await api(`projects/${id}/predict`, "POST", data); outputs.set(id, `Infrastructure fixture output (not a model):\n${result.output}\nRequest ${result.request_id} · ${result.duration_ms} ms`); }
    catch (error) { outputs.set(id, "Framework request failed; no output was produced for this attempt."); throw error; }
    finally { await refreshProject(id); }
  }, id);
};
$("#evaluate").onclick = event => action(event.currentTarget, "evaluate", async id => { try { acceptProject(await api(`projects/${id}/evaluate`, "POST")); } finally { await refreshProject(id); } });
setInterval(async () => {
  if (polling || !current || view !== "infrastructure" || !activeStates.includes(runtimeState(current).status) || ["start", "stop", "predict", "evaluate"].some(kind => isPending(kind))) return;
  polling = true;
  try { await refreshProject(current.id); } catch (error) { notice("Worker status could not be refreshed: " + error.message); }
  finally { polling = false; }
}, 5000);
$("#remove").onclick = () => { $("#remove-confirm").hidden = false; $("#remove-yes").focus(); };
$("#remove-no").onclick = () => { $("#remove-confirm").hidden = true; $("#remove").focus(); };
$("#remove-yes").onclick = event => action(event.currentTarget, "remove", async id => {
  await api("projects/" + id, "DELETE"); projects = projects.filter(project => project.id !== id);
  for (const key of drafts.keys()) if (key.startsWith(id + ":")) drafts.delete(key);
  outputs.delete(id); if (current?.id === id) { current = projects[0] || null; view = "overview"; }
  render(); notice("Workspace record removed. Model files and exported kits stay untouched.", "success");
});

const readinessMessages = {
  image_ready: ["Ready for fixture execution", "Local Linux Docker and the test image are available. Starting still requires your explicit consent."],
  image_not_prepared: ["One preparation step", "Local Linux Docker is available. Prepare the test image before starting; public packages may download."],
  remote_docker_refused: ["Remote Docker is not supported here", "Switch your Docker CLI to a local Docker Desktop or Linux socket context, then restart Studio. No remote resources were created."],
  linux_containers_required: ["Switch to Linux containers", "The fixture needs a Linux Docker engine. Switch Docker Desktop to Linux containers, then check again."],
  docker_unavailable: ["Docker is unavailable", "Install/start local Docker Desktop or Linux Docker and retry. Inspection, editing and kit export remain available."],
  docker_context_unavailable: ["Docker context could not be read", "Check that the Docker CLI has a valid local context and the engine is running, then retry."],
  timeout: ["Docker did not answer in time", "Check the local engine is running, then retry. The workspace remains usable without Docker."],
};
async function checkEnvironment() {
  const system = await api("system"), runtime = system.runtime;
  const [title, detail] = readinessMessages[runtime.code] || ["Runtime readiness is unconfirmed", "Check local Docker and retry. No images or workers were created by this check."];
  const grid = text("div", "", "system-checks");
  for (const [heading, badge, description, tone] of [
    ["Workspace", "AVAILABLE", `${system.platform} · Python ${system.python}. Local inspection, saved settings and kit export are available.`, "success"],
    [title, runtime.status === "ready" ? "READY" : "ACTION NEEDED", detail, runtime.status === "ready" ? "success" : "warning"],
  ]) {
    const card = text("div", "", "system-check"), state = text("span", badge, "state"); state.dataset.tone = tone;
    card.append(state, text("h3", heading), text("p", description)); grid.append(card);
  }
  $("#system-results").replaceChildren(grid, text("p", "Read-only check · " + new Date().toLocaleTimeString() + " · no downloads or worker start", "hint"));
}
function showEnvironment() {
  if (current) changeView("infrastructure");
  $("#environment").scrollIntoView({behavior: "instant", block: "start"});
  $("#environment-title").tabIndex = -1; $("#environment-title").focus({preventScroll: true});
}
$("#system-nav").onclick = showEnvironment;
$("#check-environment").onclick = event => action(event.currentTarget, "environment", checkEnvironment, null);
(async () => {
  try {
    projects = await api("projects"); current = projects[0] || null;
    for (const project of projects) checked.set(project.id, new Date());
    render(); if (!token) notice("Open Studio through the private session link printed by furnace studio.");
  } catch (error) { notice(error.message); }
})();
