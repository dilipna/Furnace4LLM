import test from "node:test";
import assert from "node:assert/strict";
import {countsFor, journeyFor, runtimeState, mergeProjectRecord, requestOutputFor, updateKnownProject} from "../furnace_api/studio_assets/studio-state.mjs";
import {parseCaseSuite} from "../furnace_api/studio_assets/case-import.mjs";

const importedCase = () => ({name:"Research case", input:"  preserve whitespace\n", expected_behavior:"Author-reviewed behavior"});
const parseSuite = source => parseCaseSuite(new TextEncoder().encode(source));
test("case import round-trips exported JSONL without treating labels as evidence", () => {
  const item = {...importedCase(), status:"framework_pass", recorded_status:"exact_pass"};
  assert.deepEqual(parseSuite("\ufeff\r\n" + JSON.stringify(item) + "\r\n"), {cases:[{...importedCase(), expected_output:null}], discardedStatuses:1});
});
test("case import preserves exact whitespace, Unicode code points and empty exact outputs", () => {
  const item = {...importedCase(), name:"🧪".repeat(100), expected_output:""};
  assert.deepEqual(parseSuite(JSON.stringify(item)).cases, [item]);
  assert.throws(() => parseSuite(JSON.stringify({...item, name:"🧪".repeat(101)})), /name.*invalid length/);
});
test("case import rejects malformed records without echoing their sensitive content", () => {
  for (const value of ["null", "[]", "1", '"text"', "{PRIVATE BROKEN INPUT"]) {
    assert.throws(() => parseSuite("\n" + value), error => error.message.includes("Line 2:") && !error.message.includes("PRIVATE"));
  }
  assert.throws(() => parseSuite("\n\t"), /No cases found/);
});
test("case import requires bounded typed fields and rejects unknown fields", () => {
  for (const patch of [{input:42}, {name:""}, {expected_behavior:null}, {expected_output:false}, {input:"x".repeat(4001)}, {expected_output:"x".repeat(8001)}, {api_key:"do-not-accept"}, {input:"\ud800"}]) {
    assert.throws(() => parseSuite(JSON.stringify({...importedCase(), ...patch})));
  }
});
test("case import enforces 30 cases, valid UTF-8 and the file byte limit", () => {
  const row = JSON.stringify(importedCase());
  assert.equal(parseSuite(Array(30).fill(row).join("\n")).cases.length, 30);
  assert.throws(() => parseSuite(Array(31).fill(row).join("\n")), /Line 31:.*30 cases/);
  assert.throws(() => parseCaseSuite(new Uint8Array([0xff, 0xfe])), /valid UTF-8/);
  assert.throws(() => parseCaseSuite(new Uint8Array(65537)), /exceeds 64 KiB/);
});
test("case import accounts for the normalized conditional save request size", () => {
  const items = Array.from({length:8}, () => ({name:"x", input:"i".repeat(4000), expected_behavior:"b".repeat(4000)}));
  let source = items.map(JSON.stringify).join("\n");
  items[0].expected_output = "z".repeat(65500 - source.length - ',"expected_output":""'.length);
  source = items.map(JSON.stringify).join("\n");
  assert.ok(new TextEncoder().encode(source).byteLength <= 65536);
  assert.throws(() => parseSuite(source), /normalized suite exceeds/);
});

const evidenceFor = cases => cases.map((item, case_index) => ({case_index, status: item.status}));
const bind = (project, evaluation) => ({...evaluation, project_id: project.id, configuration_sha256: project.configuration_sha256});
const prepared = () => ({
  id: "project-a", revision: 3, configuration_sha256: "current-inputs", evaluation_verification: "current_framework_evidence",
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
  project.evaluation = bind(project, {status: "interrupted", results: evidenceFor(project.cases)});
  assert.deepEqual(countsFor(project), {framework_pass: 1, framework_fail: 0, unscored: 0, error: 0, not_run: 2});
});
test("interrupted evaluations preserve mixed results without claiming completion", () => {
  const project = prepared();
  project.cases = [{status: "framework_pass"}, {status: "error"}, {status: "not_run"}];
  project.runtime = {status: "failed"};
  project.evaluation = bind(project, {status: "interrupted", results: evidenceFor(project.cases)});
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
  project.evaluation = bind(project, {status: "completed", results: evidenceFor(project.cases)});
  const journey = journeyFor(project);
  assert.equal(journey.stages.at(-1).done, true);
  assert.equal(journey.next.action, "Review results →");
  assert.equal(journey.next.download, undefined);
});
test("unscored is distinct from passed when a completed run can be exported", () => {
  const project = prepared();
  project.cases = [{status: "framework_pass"}, {status: "unscored"}];
  project.evaluation = bind(project, {status: "completed", results: evidenceFor(project.cases)});
  const journey = journeyFor(project);
  assert.equal(journey.counts.framework_pass, 1);
  assert.equal(journey.counts.unscored, 1);
  assert.equal(journey.next.download, true);
  assert.match(journey.next.description, /real model still needs its own adapter/);
});
test("a completed label with missing execution records cannot finish the journey", () => {
  const project = prepared();
  project.cases = [{status: "framework_pass"}, {status: "framework_pass"}];
  project.evaluation = bind(project, {status: "completed", results: [{}]});
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

test("a late earlier-run response cannot restore an older configuration or verdict", async () => {
  const project = prepared();
  const old = {...project, revision: 2, configuration_sha256: "old-inputs", cases: [{status: "framework_pass"}], evaluation: {status: "completed"}};
  let release;
  const delayed = new Promise(resolve => { release = resolve; });
  let state = {...project, revision: 4, evaluation: null, cases: [{status: "not_run"}]};
  const request = delayed.then(response => { state = mergeProjectRecord(state, response); });
  release(old); await request;
  assert.equal(state.revision, 4);
  assert.equal(state.configuration_sha256, "current-inputs");
  assert.equal(state.evaluation, null);
  assert.equal(countsFor(state).not_run, 1);
  assert.equal(mergeProjectRecord(state, {...state, revision: 5}).revision, 5);
});
test("project and configuration identities fence evidence and ad-hoc outputs", () => {
  const project = prepared();
  project.cases = [{status: "framework_pass"}];
  project.evaluation = bind(project, {status: "completed", results: evidenceFor(project.cases)});
  assert.equal(countsFor(project).framework_pass, 1);
  project.evaluation.project_id = "project-b";
  assert.equal(countsFor(project).framework_pass, 0);
  const output = {project_id: project.id, configuration_sha256: "old-inputs", text: "OLD OUTPUT"};
  assert.doesNotMatch(requestOutputFor(project, output), /OLD OUTPUT/);
  assert.equal(requestOutputFor(project, {...output, configuration_sha256: project.configuration_sha256}), "OLD OUTPUT");
  assert.throws(() => mergeProjectRecord(project, {...project, id: "project-b"}), /identity mismatch/);
});

test("late updates cannot recreate a deleted project or change another project", () => {
  const second = {...prepared(), id: "project-b"};
  const remaining = [second];
  assert.equal(updateKnownProject(remaining, prepared()), remaining);
  assert.equal(remaining[0], second);
  const current = [prepared(), second];
  const updated = updateKnownProject(current, {...current[0], revision: 4});
  assert.equal(updated[0].revision, 4);
  assert.equal(updated[1], second);
});
