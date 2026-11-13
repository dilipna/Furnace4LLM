import test from "node:test";
import assert from "node:assert/strict";
import {countsFor, journeyFor, runtimeState} from "../furnace_api/studio_assets/studio-state.mjs";

const evidenceFor = cases => cases.map((item, case_index) => ({case_index, status: item.status}));
const prepared = () => ({
  contract: {architecture: "Custom research architecture", notes: ""},
  plan: {compute: "customer"},
  cases: [{status: "not_run"}, {status: "not_run"}],
  runtime: "not_connected", evaluation: null,
});
test("saved preparation and detected files never establish execution", () => {
  const project = prepared();
  project.assessment = {file_evidence: {checkpoint_file_present: true}};
  const journey = journeyFor(project);
  assert.equal(journey.stages.filter(s => s.done).length, 4);
  assert.equal(journey.stages.at(-1).done, false);
  assert.equal(journey.next.view, "infrastructure");
  assert.equal(runtimeState(project).status, "not_connected");
});
test("an unsupported or absent case status is missing evidence, never a pass", () => {
  const project = prepared();
  project.cases = [{status: "framework_pass"}, {status: "future_status"}, {}];
  project.evaluation = {status: "interrupted", results: evidenceFor(project.cases)};
  assert.deepEqual(countsFor(project), {framework_pass: 1, framework_fail: 0, unscored: 0, error: 0, not_run: 2});
});
test("interrupted evaluations preserve mixed results without claiming completion", () => {
  const project = prepared();
  project.cases = [{status: "framework_pass"}, {status: "error"}, {status: "not_run"}];
  project.runtime = {status: "failed"};
  project.evaluation = {status: "interrupted", results: evidenceFor(project.cases)};
  const journey = journeyFor(project);
  assert.equal(journey.stages.at(-1).done, false);
  assert.equal(journey.next.action, "Recover worker →");
  assert.equal(journey.counts.framework_pass, 1);
  assert.equal(journey.counts.error, 1);
  assert.equal(journey.counts.not_run, 1);
});
test("completed run with an unfavorable assertion sends users to its results", () => {
  const project = prepared();
  project.cases = [{status: "framework_pass"}, {status: "framework_fail"}];
  project.evaluation = {status: "completed", results: evidenceFor(project.cases)};
  const journey = journeyFor(project);
  assert.equal(journey.stages.at(-1).done, true);
  assert.equal(journey.next.action, "Review results →");
  assert.equal(journey.next.download, undefined);
});
test("unscored is distinct from passed when a completed run can be exported", () => {
  const project = prepared();
  project.cases = [{status: "framework_pass"}, {status: "unscored"}];
  project.evaluation = {status: "completed", results: evidenceFor(project.cases)};
  const journey = journeyFor(project);
  assert.equal(journey.counts.framework_pass, 1);
  assert.equal(journey.counts.unscored, 1);
  assert.equal(journey.next.download, true);
  assert.match(journey.next.description, /real model still needs its own adapter/);
});
test("a completed label with missing execution records cannot finish the journey", () => {
  const project = prepared();
  project.cases = [{status: "framework_pass"}, {status: "framework_pass"}];
  project.evaluation = {status: "completed", results: [{}]};
  assert.equal(journeyFor(project).stages.at(-1).done, false);
});
test("unknown cleanup requires recovery even if prior evidence exists", () => {
  const project = prepared();
  project.runtime = {status: "unknown"};
  assert.equal(journeyFor(project).next.title, "Resolve the worker’s cleanup state");
});
test("a ready worker leads to actual evaluation rather than assuming success", () => {
  const project = prepared();
  project.runtime = {status: "ready"};
  assert.equal(journeyFor(project).next.action, "Open evaluations →");
  project.contract = {architecture: "", notes: ""};
  assert.equal(journeyFor(project).next.view, "contract");
});

test("legacy cached case labels without their evaluation record are not evidence", () => {
  const project = prepared();
  project.cases = [{status: "framework_pass"}, {status: "unscored"}];
  assert.equal(countsFor(project).framework_pass, 0);
  assert.equal(countsFor(project).not_run, 2);
  assert.equal(journeyFor(project).stages.at(-1).done, false);
});
