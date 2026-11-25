import {recommendedSelection} from "./everyday-selection.mjs";
const $ = value => document.querySelector(value);
const fragment = new URLSearchParams(location.hash.slice(1)).get("session");
const token = fragment || sessionStorage.getItem("furnace-session") || "";
if (fragment) { sessionStorage.setItem("furnace-session", fragment); history.replaceState(null, "", "/"); }
let chatTurns = [], setupWorking = false, answerController = null, settingsEdited = false, refreshAgain = false, includeAiText = false;
let documentText = "", action = "chat", projectId = "", epoch = 0, busy = false, refreshing = false, selectionChosen = false, hardwareChosen = false;
const labels = {summarise:"Summarise",ask:"Ask about this document",actions:"Extract action items",dates:"Find dates",rewrite:"Simplify",reply:"Draft a reply",translate:"Translate",chat:"Chat"};
const errors = {
  endpoint_timeout:"The local AI took too long; that request was cancelled. Try shorter text. Furnace checks the same connection before your next request.",
  endpoint_unavailable_or_invalid:"The local AI is unavailable. Check its state in Model & setup before trying again.",
  connect_current_model_configuration_first:"Reconnect the current model in Advanced, or stop and start it from setup.",
  managed_server_not_running:"Start your local AI in Model & setup first.",
  stop_managed_server_first:"Stop the current model before changing its settings.",
  prepare_managed_model_first:"Download and prepare the selected model before starting it.",
  managed_server_already_running:"The model is already running. Close setup to work with a document.",
  docker_unavailable:"Docker is not reachable. Open Docker Desktop and wait for the automatic recheck.",
  linux_containers_required:"Switch Docker Desktop to Linux containers, then wait for the recheck.",
  gpu_runtime_unavailable:"Docker GPU access is unavailable. Choose CPU, or configure GPU access before starting.",
  memory_exceeds_docker_limit:"The model's memory request exceeds Docker's allocation. Review Docker memory or choose a smaller model.",
  artifact_digest_mismatch:"The saved weights failed their integrity check and were rejected. Prepare again to download a verified copy.",
  download_digest_mismatch:"The downloaded weights failed their integrity check and were not used. Prepare again.",
};
const message = text => { $("#notice").textContent = text; };
async function api(path, method="GET", body) {
  const response = await fetch("/api/"+path, {method, headers:{"x-furnace-session":token,"Content-Type":"application/json"}, ...(body === undefined ? {} : {body:JSON.stringify(body)})});
  const data = await response.json().catch(() => ({detail:response.status === 401 ? "Reopen Furnace from its app window to reconnect." : "The local app could not complete this request."}));
  if (!response.ok) throw new Error(typeof data.detail === "string" ? (errors[data.detail] || data.detail.replaceAll("_"," ")) : "Check the form fields and try again.");
  return data;
}
function setBusy(value) {
  busy=value; document.body.classList.toggle("busy",value);
  for (const element of document.querySelectorAll("#send,.task-list button,#choose-file,#use-text,#project,#file")) element.disabled=value || setupWorking;
  $("#composer").setAttribute("aria-busy", String(value));
}
function setAction(value) {
  action=value;
  $("#task-label").textContent=(value === "chat" ? "Chat · recent context only" : labels[value])+(documentText ? " · selected document" : " · no document selected");
  for (const button of document.querySelectorAll("[data-action]")) button.setAttribute("aria-pressed",String(button.dataset.action===value));
  $("#question").placeholder=value === "translate" ? "Target language, e.g. Spanish" : value === "ask" ? "What would you like to know about this document?" : "What would you like help with?";
  $("#question-label").textContent=value === "translate" ? "Translate into which language?" : value === "ask" ? "Ask about this document" : "Ask something, or just chat";
}
function resetProtection() {
  includeAiText=false; $("#document-protection").hidden=true;
  $("#set-aside-text").textContent=""; $("#set-aside-summary").textContent=""; $("#set-aside-count").textContent="";
  $("#include-ai").textContent="Include it anyway";
}
function clearConversation() {
  if(answerController) answerController.abort();
  epoch++; chatTurns=[]; documentText=""; resetProtection(); $("#document-text").value=""; $("#question").value=""; $("#file").value="";
  $("#conversation").replaceChildren(); $("#document-info").textContent="Drop a PDF, Word document, TXT or Markdown file here.";
  setAction("chat"); message(busy ? "Conversation cleared. A request already sent locally may finish; its answer will be discarded." : "Conversation cleared from this tab. Original files are unchanged.");
}
$("#clear").addEventListener("click",clearConversation);
window.addEventListener("pageshow",event=>{if(event.persisted) clearConversation();});
$("#choose-file").addEventListener("click",()=>$("#file").click());
async function readFile(file) {
  if (busy || !file) return;
  if (file.size>3000000) { message("Choose a file smaller than 3 MB."); return; }
  const kind=file.name.split(".").at(-1).toLowerCase();
  if (!["pdf","docx","txt","md"].includes(kind)) { message("Choose PDF, DOCX, TXT or Markdown."); return; }
  const generation=++epoch;
  chatTurns=[]; documentText=""; resetProtection(); setBusy(true); message("Reading document locally. Nothing is uploaded to a cloud service.");
  try {
    const bytes=new Uint8Array(await file.arrayBuffer());
    let binary=""; for (let i=0;i<bytes.length;i+=16384) binary+=String.fromCharCode(...bytes.subarray(i,i+16384));
    const result=await api("everyday/extract","POST",{kind,data:btoa(binary)});
    if (generation!==epoch) return;
    if (new TextEncoder().encode(result.text).length>128000) throw new Error("Document exceeds 128,000 UTF-8 text bytes. Split it into smaller files.");
    documentText=result.text; $("#document-info").textContent=file.name+" · read locally · "+documentText.length.toLocaleString()+" characters";
    setAction("summarise"); await inspectDocument(); if(generation!==epoch) return; message("Document ready. Choose an action below. Longer documents are processed in stages. "+(result.warning || ""));
  } catch(error) { if(generation===epoch) message(error.message); }
  finally { setBusy(false); }
}
$("#file").addEventListener("change",event=>readFile(event.target.files[0]));
const drop=$("#document-box");
drop.addEventListener("dragover",event=>{event.preventDefault();drop.classList.add("drag");});
drop.addEventListener("dragleave",()=>drop.classList.remove("drag"));
drop.addEventListener("drop",event=>{event.preventDefault();drop.classList.remove("drag");readFile(event.dataTransfer.files[0]);});
$("#use-text").addEventListener("click",async ()=>{
  const value=$("#document-text").value;
  if(!value.trim()) { message("Paste document text first."); return; }
  if(new TextEncoder().encode(value).length>128000) { message("Use at most 128,000 UTF-8 text bytes."); return; }
  epoch++; chatTurns=[]; documentText=value; $("#document-info").textContent="Pasted document · "+value.length.toLocaleString()+" characters";
  const generation=epoch;
  $("#paste").open=false; setAction("summarise"); await inspectDocument(); if(generation!==epoch) return; message("Pasted text ready. It is not saved in project records.");
});
async function inspectDocument() {
  resetProtection();
  const generation=epoch;
  try {
    const result=await api("everyday/inspect","POST",{text:documentText,action:"summarise"});
    if(generation!==epoch) return;
    $("#document-protection").hidden=!result.sentences.length;
    $("#set-aside-text").textContent=result.sentences.join("");
    $("#set-aside-count").textContent=result.sentences.length;
    $("#set-aside-summary").textContent=result.sentences.length===1 ? "1 sentence addressed to an AI was set aside." : result.sentences.length+" sentences addressed to an AI were set aside.";
    $("#include-ai").textContent="Include it anyway";
  } catch(error) {if(generation===epoch) message(error.message);}
}
$("#include-ai").addEventListener("click",()=>{
  if(busy) return;
  includeAiText=!includeAiText;
  $("#include-ai").textContent=includeAiText ? "Set it aside again" : "Include it anyway";
  $("#set-aside-summary").textContent=includeAiText ? "AI-directed text will be included by your choice. Check answers carefully." : $("#set-aside-count").textContent+" sentence(s) addressed to an AI set aside.";
});
function element(tag,text,className) { const item=document.createElement(tag);if(text!==undefined) item.textContent=text;if(className)item.className=className;return item; }
function renderAnswer(result,label,question) {
  const article=element("article",undefined,"answer");
  for(const warning of result.warnings || []) { const note=element("p",warning,"document-warning"); note.setAttribute("role","note"); article.append(note); }
  if(question) article.append(element("p",question,"user-message"));
  article.append(element("h2",label),element("div",result.output,"output"));
  if(result.protection?.included && result.protection.sentences.length) article.append(element("p","AI-directed text was included by your choice.","document-warning"));
  if(result.sources?.length) {
    const sources=element("details"); sources.append(element("summary","Source references: "+result.sources.map(s=>"Section "+s.section).join(", ")));
    sources.append(element("p","Text supplied after any set-aside removal. These are Furnace text sections, not original page or clause numbers. References do not prove that every answer claim is supported; check the text below."));
    for(const source of result.sources) sources.append(element("h3","Text section "+source.section),element("pre",source.text,"source-text"));
    article.append(sources);
  }
  const seconds=(result.duration_ms/1000).toFixed(1);
  article.append(element("p",`${seconds}s total · ${result.processing.model_requests} local request(s) · ${result.receipt.model.id}`,"meta"));
  if(result.processing.history_truncated) article.append(element("p","Recent chat context was shortened to fit this model. Include key details again if needed.","meta"));
  if(result.processing.staged) article.append(element("p",`Processed ${result.processing.document_chunks} document sections in stages. ${result.processing.method}. Cross-section context can be lost; check the original.`,"meta"));
  const receipt=element("details",undefined,"receipt");
  receipt.append(element("summary",result.receipt.status==="checked" ? "✓ Answered on this computer · Model had no internet route at checks · Details" : "Privacy receipt · test adapter, not real Docker proof"));
  receipt.append(element("p","These are checks of the model container and this app's handling, not proof about every program on your computer."));
  const list=element("ul");
  for(const [key,passed] of Object.entries(result.receipt.observed.checks)) list.append(element("li",`${key.replaceAll("_"," ")}: ${passed ? "observed" : "not confirmed"}`));
  receipt.append(list,element("p",result.receipt.data_handling));
  const technical=element("details"); technical.append(element("summary","Model identity and technical details"));
  technical.append(element("p",`Recorded ${result.receipt.at} · launch ${result.receipt.launch_id}`));
  technical.append(element("p",`Pinned revision: ${result.receipt.model.revision}`),element("p",`Weights SHA-256: ${result.receipt.model.weights_sha256}`),element("p",result.receipt.model.weights_check),element("p",result.receipt.scope));
  receipt.append(technical); article.append(receipt); $("#conversation").append(article); article.scrollIntoView({block:"nearest"});
}
async function streamAnswer(pid,payload,onProgress,signal) {
  const response=await fetch(`/api/everyday/projects/${pid}/answer-stream`,{method:"POST",headers:{"Content-Type":"application/json","x-furnace-session":token},body:JSON.stringify(payload),signal});
  if(!response.ok) { const error=await response.json(); throw new Error(typeof error.detail==="string" ? error.detail : "Check the document and model setup."); }
  const reader=response.body.getReader(), decoder=new TextDecoder();
  let buffer="", answer;
  while(true) {
    const part=await reader.read(); buffer+=decoder.decode(part.value,{stream:!part.done});
    let boundary;
    while((boundary=buffer.indexOf("\n"))>=0) {
      const line=buffer.slice(0,boundary); buffer=buffer.slice(boundary+1);
      if(!line) continue;
      const event=JSON.parse(line);
      if(event.error) throw new Error(event.error);
      if(event.progress) onProgress(event.progress);
      if(event.result) answer=event.result;
    }
    if(part.done) break;
  }
  if(!answer) throw new Error("The local answer was interrupted. Check the model and try again.");
  return answer;
}
async function send() {
  if(busy) return;
  if(!projectId) { message("Set up and start your local AI first. Downloads need your approval."); await showSetup(); return; }
  if(action!=="chat" && !documentText) { message("Choose a document or paste its text first."); return; }
  const question=$("#question").value.trim();
  if(["ask","chat","translate"].includes(action) && !question) { $("#question").focus();message("Enter a question, message or target language.");return; }
  const generation=epoch, pid=projectId, label=labels[action];
  const controller=new AbortController(); answerController=controller;
  setBusy(true); message("Planning the local request…");
  try {
    let truncated=false;
    const history=action==="chat" && !documentText ? chatTurns.slice(-2).map(turn=>{
      let content="";
      for(const char of turn.content) {
        if(new TextEncoder().encode(content+char).length>300) {truncated=true;break;}
        content+=char;
      }
      return {role:turn.role,content};
    }) : [];
    const payload={text:documentText,question,action,history,history_truncated:truncated,include_ai_text:includeAiText};
    const plan=await api("everyday/projects/"+pid+"/plan","POST",payload);
    if(generation!==epoch || projectId!==pid) return;
    const estimate="Rough estimate: "+plan.estimate_seconds.join("–")+" seconds. "+plan.estimate_basis+" No cloud fallback.";
    message(estimate);
    if(plan.document_sections>1 && !confirm(estimate+" Continue?")) return;
    const result=await streamAnswer(pid,payload,event=>{
      if(generation!==epoch || projectId!==pid) return;
      const n=event.completed_requests, sections=event.document_sections;
      const left=event.phase==="document" ? Math.max(0,sections-n)+Math.ceil(sections/4)+1 : 1;
      const estimate=n>0 ? ` Rough estimate: ${Math.max(1,Math.round(left*event.elapsed_seconds/n/60))}–${Math.max(1,Math.ceil(left*event.elapsed_seconds/n*2/60))} minutes remaining; combining stages may add time.` : " Estimating after the first section.";
      message(`Working locally · ${n} requests completed · ${sections} document sections · ${event.phase==="combining" ? "combining results" : "reading sections"}.${estimate}`);
    },controller.signal);
    if(generation!==epoch || projectId!==pid) return;
    renderAnswer(result,label,question);
    if(action==="chat" && !documentText) chatTurns=[{role:"user",content:question},{role:"assistant",content:result.output}]; $("#question").value="";message("Answer complete. Check important details and inspect the privacy receipt.");
  } catch(error) { if(generation===epoch) message(error.message); }
  finally {if(answerController===controller) answerController=null;setBusy(false);}
}
$("#composer").addEventListener("submit",event=>{event.preventDefault();send();});
for(const button of document.querySelectorAll("[data-action]")) button.addEventListener("click",()=>{
  setAction(button.dataset.action);
  if(["ask","translate","reply"].includes(action)) {$("#question").focus();return;}
  send();
});
async function refresh() {
  if(refreshing || setupWorking) {refreshAgain=true;return;}
  refreshAgain=false; refreshing=true;
  const generation=epoch;
  try {
    const catalog=await api("managed/catalog");
    const docker=catalog.docker;
    if(!hardwareChosen) {
      const hardware=await api("everyday/hardware");
      if(generation!==epoch) return;
      const gpu=hardware.gpu;
      const recommended=recommendedSelection(docker,gpu);
      $("#accelerator").value=recommended.accelerator; $("#model-choice").value=recommended.model;
      hardwareChosen=docker.status==="ready";
    }
    $("#docker-state").textContent=docker.status==="ready" ? "Docker is ready with Linux containers." : docker.status==="linux_containers_required" ? "Switch Docker Desktop to Linux containers. This page rechecks automatically." : "Docker is not reachable. Open Docker Desktop; this page rechecks automatically.";
    const projects=await api("projects");
    if(generation!==epoch || setupWorking) return;
    const selected=projects.find(p=>p.id===projectId) || (!selectionChosen && (projects.find(p=>p.origin==="everyday") || projects.find(p=>p.managed_server?.status==="ready" && !p.managed_server?.selection?.python)));
    const select=$("#project");
    if(!busy) {
      select.replaceChildren(new Option("Create private-document workspace",""));
      for(const project of projects.filter(p=>!p.managed_server?.selection?.python)) select.add(new Option(project.name,project.id));
    }
    if(selected) {
      projectId=selected.id;select.value=projectId;
      const managed=await api(`projects/${selected.id}/managed`);
      if(generation!==epoch || setupWorking) return;
      if(managed.selection && !settingsEdited) {
        if(![...$("#model-choice").options].some(option=>option.value===managed.selection.model)) {
          const saved=catalog.models.find(model=>model.id===managed.selection.model);
          if(saved) $("#model-choice").add(new Option(saved.name+" (existing Advanced selection)",saved.id));
        }
        $("#model-choice").value=managed.selection.model;
        $("#accelerator").value=managed.selection.accelerator;
      }
      $("#model-status").textContent=managed.status==="ready" ? `${managed.selection.model.includes("4b-q4") ? "Quality" : managed.selection.model.includes("1.5b") ? "Everyday" : "Local"} AI · ${managed.selection.accelerator==="nvidia" ? "GPU" : "CPU"} · ready` : "Local AI · "+(managed.status || "not set up");
      if($("#setup").open) $("#setup-status").textContent=managed.status==="preparing" ? "Preparing approved files… "+(managed.preparation?.phase || "") : managed.reason || (managed.status || "Choose a model and approve its preparation.");
    } else {$("#model-status").textContent="Set up local AI";projectId="";}
  } catch(error) {$("#model-status").textContent="Studio disconnected";if($("#setup").open) $("#setup-status").textContent=error.message;}
  finally {refreshing=false;if(refreshAgain && !setupWorking) {refreshAgain=false;queueMicrotask(refresh);}}
}
async function showSetup() {$("#setup").showModal();await refresh();}
$("#setup-open").addEventListener("click",showSetup);$("#model-status").addEventListener("click",showSetup);
for(const selector of ["#accelerator","#model-choice"]) $(selector).addEventListener("change",()=>{hardwareChosen=true;settingsEdited=true;});
$("#project").addEventListener("change",event=>{projectId=event.target.value;selectionChosen=true;settingsEdited=false;hardwareChosen=false;clearConversation();$("#model-status").textContent="Checking workspace…";refresh();});
async function setupAction(kind) {
  if(["prepare","start"].includes(kind) && $("#model-choice").value==="qwen3-4b-q4_k_m" && $("#accelerator").value!=="nvidia") {$("#setup-status").textContent="The quality option is for a compatible NVIDIA GPU. Choose Qwen2.5-1.5B for CPU or open Advanced for experimental settings.";return;}
  if(kind==="start" && settingsEdited) {$("#setup-status").textContent="Prepare the selected settings before starting. The saved model has not been changed.";return;}
  if(kind!=="stop" && !$("#consent").checked) {$("#setup-status").textContent="Approve the download and execution before proceeding.";return;}
  setupWorking=true;
  for(const control of document.querySelectorAll(".setup-actions button,#project,#model-choice,#accelerator,#consent")) control.disabled=true;
  try {
    const pid=projectId || (await api("everyday/setup","POST")).id;
    projectId=pid;
    if(kind==="prepare") {
      await api(`projects/${pid}/managed`,"PUT",{model:$("#model-choice").value,accelerator:$("#accelerator").value,memory_mb:$("#model-choice").value.includes("0.5b") ? 2048 : 4096,context_tokens:4096,max_tokens:512,request_timeout_seconds:120});
      await api(`projects/${pid}/managed/prepare`,"POST",{consent:true});
      settingsEdited=false;
      $("#setup-status").textContent="Preparing the approved model. Wait for prepared, then press Start.";
    } else {
      if(kind==="stop" && !confirm("Stop this local model? An in-progress answer may be interrupted.")) return;
      const result=await api(`projects/${pid}/managed/${kind}`,"POST",kind==="start" ? {consent:true} : undefined);
      $("#setup-status").textContent=result.status==="ready" ? "Your local AI is ready. Close setup to work with a document." : result.reason || result.status;
    }

  } catch(error) {$("#setup-status").textContent=error.message;}
  finally {
    setupWorking=false;
    for(const control of document.querySelectorAll(".setup-actions button,#project,#model-choice,#accelerator,#consent")) control.disabled=false;
    $("#project").disabled=busy;
    refresh();
  }
}
for(const kind of ["prepare","start","stop"]) $("#"+kind).addEventListener("click",()=>setupAction(kind));
refresh();
setInterval(()=>{if(document.visibilityState==="visible") refresh();},10000);
