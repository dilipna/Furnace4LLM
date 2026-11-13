"use strict";
const $ = (s) => document.querySelector(s);
let token = new URLSearchParams(location.hash.slice(1)).get("session") || sessionStorage.getItem("furnace-session");
if (token) { sessionStorage.setItem("furnace-session", token); history.replaceState(null, "", location.pathname); }
let projects = [], current = null, view = "overview";
function notice(text) { $("#notice").textContent = text; }
async function api(path, method="GET", data) {
  const response = await fetch("/api/"+path, {method, headers:{"X-Furnace-Session":token || "", ...(data ? {"Content-Type":"application/json"} : {})}, body:data ? JSON.stringify(data) : undefined});
  if (!response.ok) { let message = ""; try { const body = await response.json(); message = typeof body.detail === "string" ? body.detail : "Check the form values."; } catch { message = response.status === 401 ? "Session unavailable. Reopen the local session link printed by furnace studio." : "Workspace request failed. Check the local application is running."; } throw new Error(message); }
  return response.status === 204 ? null : response.headers.get("content-type")?.includes("application/zip") ? response.blob() : response.json();
}
function text(tag, content, className) { const e=document.createElement(tag); e.textContent=content; if(className)e.className=className; return e; }
async function action(button, fn) { button.disabled=true; notice(""); try { await fn(); } catch(e) { notice(e.message); } finally { button.disabled=false; } }
function navigation() {
  $("#count").textContent=projects.length+" / 2";
  $("#projects").replaceChildren(...projects.map(p=> { const b=text("button",p.name,"project-button"); b.append(text("small","Model not connected")); if(current?.id===p.id)b.setAttribute("aria-current","true"); b.onclick=()=>{current=p;view="overview";render();}; return b; }));
}
function changeView(next) { view=next; renderPanels(); }
function renderPanels() {
  document.querySelectorAll("[data-panel]").forEach(p=>p.hidden=p.dataset.panel!==view);
  document.querySelectorAll("[data-view]").forEach(b=> { if(b.dataset.view===view)b.setAttribute("aria-current","page");else b.removeAttribute("aria-current"); });
}
function render() {
  navigation(); $("#welcome").hidden=!!current; $("#workspace").hidden=!current;
  if(!current)return;
  $("#project-title").textContent=current.name; $("#project-path").textContent=current.path;
  const labels={configuration_file_present:"Configuration",checkpoint_file_present:"Checkpoint files",python_source_present:"Python source",dependency_manifest_present:"Dependencies",test_files_present:"Test files"};
  $("#evidence").replaceChildren(...Object.entries(current.assessment.file_evidence).map(([key,value])=>text("span",labels[key]+(value?" · detected":" · not detected"),"chip"+(value?"":" missing"))));
  const titles={model_loading:"Model loading",serving_and_harness:"Serving & harness",security:"Security boundaries",evaluations:"Evaluations",logs_and_metrics:"Logs & metrics",operations:"Operations & recovery"};
  $("#capabilities").replaceChildren(...current.assessment.capabilities.map(c=>{const card=text("article","","capability");card.append(text("span","UNVERIFIED","state"),text("h3",titles[c.area]||c.area),text("p",c.next_action));return card;}));
  $("#warnings").hidden=!current.assessment.warnings.length; $("#warnings").textContent=current.assessment.warnings.join(" · ");
  for(const [key,value] of Object.entries(current.contract))$("#contract-form").elements.namedItem(key).value=value;
  $("#plan-form").reset(); if(current.plan)for(const key of ["compute","memory_gb","timeout_seconds","log_retention_days"])$("#plan-form").elements.namedItem(key).value=current.plan[key];
  $("#runtime-message").textContent="Awaiting a validated model adapter. No model server is running.";
  $("#cases").replaceChildren(...current.cases.map((c,i)=>{const card=text("article","","case");card.append(text("span","NOT RUN","state"),text("h3",c.name),text("p","Input: "+c.input),text("p","Expected: "+c.expected_behavior)); const remove=text("button","Remove case","secondary");remove.onclick=()=>action(remove,async()=>{await update("cases",{cases:current.cases.filter((_,j)=>i!==j).map(({name,input,expected_behavior})=>({name,input,expected_behavior}))});});card.append(remove);return card;}));
  if(!current.cases.length)$("#cases").append(text("p","No evaluation cases yet. Add one above; it will stay Not run until real model execution is connected."));
  $("#events").replaceChildren(...[...current.events].reverse().map(e=>{const li=text("li",e.message);const time=text("time",new Date(e.at).toLocaleString());time.dateTime=e.at;li.prepend(time);return li;}));
  $("#remove-confirm").hidden=true;renderPanels();
}
async function update(field,data) { current=await api("projects/"+current.id+"/"+field,"PUT",data);projects=projects.map(p=>p.id===current.id?current:p);render();notice("Saved locally. No model execution or provisioning occurred."); }
$("#new-project").onclick=()=>{current=null;render();$("#add-form input").focus();};
$("#sections").onclick=e=>{const b=e.target.closest("[data-view]");if(b)changeView(b.dataset.view);};
$("#add-form").onsubmit=e=>{e.preventDefault();const form=e.currentTarget;action(form.querySelector("button"),async()=>{current=await api("projects","POST",Object.fromEntries(new FormData(form)));projects=await api("projects");view="overview";form.reset();render();$("#project-title").tabIndex=-1;$("#project-title").focus();});};
$("#contract-form").onsubmit=e=>{e.preventDefault();const f=e.currentTarget;action(f.querySelector("button"),()=>update("contract",Object.fromEntries(new FormData(f))));};
$("#plan-form").onsubmit=e=>{e.preventDefault();const f=e.currentTarget;const data=Object.fromEntries(new FormData(f));for(const k of ["memory_gb","timeout_seconds","log_retention_days"])data[k]=Number(data[k]);action(f.querySelector("button"),()=>update("plan",data));};
$("#case-form").onsubmit=e=>{e.preventDefault();const f=e.currentTarget;action(f.querySelector("button"),async()=>{const cases=current.cases.map(({name,input,expected_behavior})=>({name,input,expected_behavior}));cases.push(Object.fromEntries(new FormData(f)));await update("cases",{cases});f.reset();});};
$("#download").onclick=e=>action(e.currentTarget,async()=>{const blob=await api("projects/"+current.id+"/kit","POST");const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download="furnace-starter-kit.zip";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);notice("Starter kit downloaded. It includes your saved assessment and configuration; no infrastructure has been provisioned.");});
$("#start").onclick=e=>action(e.currentTarget,()=>api("projects/"+current.id+"/start","POST"));
$("#remove").onclick=()=>{$("#remove-confirm").hidden=false;$("#remove-yes").focus();};
$("#remove-no").onclick=()=>{$("#remove-confirm").hidden=true;$("#remove").focus();};
$("#remove-yes").onclick=e=>action(e.currentTarget,async()=>{await api("projects/"+current.id,"DELETE");projects=await api("projects");current=projects[0]||null;view="overview";render();notice("Workspace record removed. Model files and exports were not changed.");});
(async()=>{try{projects=await api("projects");current=projects[0]||null;render();if(!token)notice("Open Studio through the session link printed by furnace studio.");}catch(e){notice(e.message);}})();
