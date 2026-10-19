import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { checkPrefix, exampleSnapshots, MAX_BYTES } from "./prefix-check.ts";

const study = new URL("../../../experiments/prefix-cache/", import.meta.url);
const read = path => readFileSync(new URL(path, study), "utf8");
const replay = JSON.parse(read("guard-replay.json"));
const manifest = JSON.parse(read(`runs/${replay.campaign}/manifest.json`));
for (const expected of replay.results) {
  test(`matches actual Python Forge replay: ${expected.condition}, repeat ${expected.repeat}`, () => {
    const find = condition => manifest.attempts.find(r => r.status === "success" && r.repeat === expected.repeat && r.condition === condition);
    const result = checkPrefix(read(`${find("A").path}/workload.jsonl`), read(`${find(expected.condition).path}/workload.jsonl`));
    assert.equal(result.status, expected.status);
    assert.equal(result.baseShared, expected.base_shared_chars);
    assert.equal(result.headShared, expected.shared_chars);
    assert.equal(result.required, expected.required_chars);
  });
}
test("synthetic regression and repair demonstrate the actual checker", () => {
  for (const fixed of [false, true]) {
    const { base, head } = exampleSnapshots(fixed);
    assert.equal(checkPrefix(base, head).status, fixed ? "PASS" : "FAIL");
  }
});
const snapshot = (prefix, questions = ["A", "B"]) => questions.map(content => JSON.stringify({messages: [{role: "system", content: prefix}, {role: "user", content}]})).join("\n");
test("counts Unicode code points like Python, not UTF-16 units", () => {
  const source = snapshot("🙂".repeat(20));
  assert.equal(checkPrefix(source, source).baseShared, 33); // system\n + 20 + \nuser\n
});
test("weak baseline is inconclusive", () => {
  const source = ["A", "B"].map(content => JSON.stringify({messages: [{role: "user", content}]})).join("\n");
  assert.equal(checkPrefix(source, source).status, "INCONCLUSIVE");
});
test("rejects invalid, duplicate, unmatched and multimodal requests", () => {
  const valid = snapshot("stable instructions");
  for (const bad of ["", "{}\n{}", "broken\njson", snapshot("x", ["A", "A"]), snapshot("x", ["B", "A"]), snapshot("x", ["A", "B", "C"]), '{"messages":[{"role":"user","content":[]}]}\n{}', '{"messages":[{"role":"assistant","content":"x"}]}\n{}']) {
    assert.throws(() => checkPrefix(valid, bad));
  }
});
test("limits bytes and row counts before expensive comparisons", () => {
  const valid = snapshot("stable instructions");
  assert.throws(() => checkPrefix("x".repeat(MAX_BYTES + 1), valid), /2 MiB/);
  assert.throws(() => checkPrefix(Array(201).fill("{}").join("\n"), valid), /2–200/);
});
