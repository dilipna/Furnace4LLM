// Presentation rules use saved execution evidence, never file presence as proof.
export const activeStates = ["ready", "starting", "unknown"];
export function runtimeState(project) {
  return typeof project.runtime === "object" && project.runtime !== null
    ? project.runtime : {status: "not_connected", reason: "No model adapter is connected."};
}
export function caseStatus(project, index) {
  const status = project.cases[index]?.status;
  if (!["framework_pass", "framework_fail", "unscored", "error", "not_run"].includes(status)) return "not_run";
  const evidence = project.evaluation?.results?.find(result => result.case_index === index && result.status === status);
  return evidence ? status : "not_run";
}
export function countsFor(project) {
  const counts = {framework_pass: 0, framework_fail: 0, unscored: 0, error: 0, not_run: 0};
  for (const [index] of project.cases.entries()) {
    const status = caseStatus(project, index);
    const key = Object.hasOwn(counts, status) ? status : "not_run";
    counts[key] += 1;
  }
  return counts;
}
export function journeyFor(project) {
  const counts = countsFor(project);
  const contract = Boolean(project.contract.architecture?.trim() || project.contract.notes?.trim());
  const execution = project.cases.length > 0 && project.evaluation?.status === "completed"
    && project.evaluation.results?.length === project.cases.length && !counts.not_run && !counts.error;
  const stages = [
    {label: "Project inspected", view: "overview", done: true},
    {label: "Interface described", view: "contract", done: contract},
    {label: "Compute preferences", view: "infrastructure", done: Boolean(project.plan)},
    {label: "Cases prepared", view: "evaluations", done: project.cases.length > 0},
    {label: "Framework executed", view: "evaluations", done: execution},
  ];
  const state = runtimeState(project).status;
  let next;
  if (!contract) next = {view: "contract", title: "Describe the model interface", description: "Capture its architecture or loading notes so the adapter requirements are explicit.", action: "Describe model →"};
  else if (!project.plan) next = {view: "infrastructure", title: "Choose your compute preferences", description: "Save the intended environment. No cloud resource or subscription is activated.", action: "Choose preferences →"};
  else if (!project.cases.length) next = {view: "evaluations", title: "Prepare your first evaluation case", description: "Define a sanitized input and an expected behavior. Add an exact assertion to score the fixture.", action: "Add a case →"};
  else if (state === "unknown") next = {view: "infrastructure", title: "Resolve the worker’s cleanup state", description: "Recover local Docker, refresh status and retry Stop. Cleanup has not been confirmed.", action: "Check worker →"};
  else if (["failed", "interrupted"].includes(state) && !execution) next = {view: "infrastructure", title: "Restart the interrupted worker", description: "Completed case evidence is retained. Start explicitly before running another attempt.", action: "Recover worker →"};
  else if (execution && counts.framework_fail) next = {view: "evaluations", title: "Review the failed exact assertions", description: "The run completed, but some outputs did not match. Inspect the expectations before changing them.", action: "Review results →"};
  else if (execution) next = {view: "overview", title: "Take your evidence with you", description: "Export the saved kit and framework results. A real model still needs its own adapter and acceptance tests.", action: "Download evidence ↓", download: true};
  else if (state === "ready") next = {view: "evaluations", title: "Run your prepared framework checks", description: "The worker is ready. Exact outputs can be checked; descriptive expectations remain unscored.", action: "Open evaluations →"};
  else next = {view: "infrastructure", title: "Try the isolated infrastructure runtime", description: "Check this machine, prepare the test image and explicitly start the fixture. It is not a model.", action: "Open local runtime →"};
  return {stages, next, counts};
}
export function toneFor(status) {
  if (["ready", "framework_pass"].includes(status)) return "success";
  if (["failed", "framework_fail", "error"].includes(status)) return "error";
  if (["unknown", "interrupted", "starting", "not_run"].includes(status)) return "warning";
  return "neutral";
}
