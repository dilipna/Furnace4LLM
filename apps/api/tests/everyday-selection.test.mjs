import test from "node:test";
import assert from "node:assert/strict";
import {recommendedSelection} from "../furnace_api/studio_assets/everyday-selection.mjs";

const ready = {status: "ready", gpu_runtime: true};
const gpu = {name: "NVIDIA", memory_total_mib: 4096, memory_used_mib: 250};
test("quality recommendation requires observed free memory and Docker GPU access", () => {
  assert.deepEqual(recommendedSelection(ready, gpu), {model:"qwen3-4b-q4_k_m", accelerator:"nvidia"});
});
test("a busy compatible GPU gets the faster option rather than an assumed 4B fit", () => {
  assert.deepEqual(recommendedSelection(ready, {...gpu,memory_used_mib:1500}), {model:"qwen2.5-1.5b-instruct-q4_k_m", accelerator:"nvidia"});
});
test("insufficient free GPU memory chooses CPU", () => {
  assert.equal(recommendedSelection(ready, {...gpu,memory_used_mib:3000}).accelerator,"cpu");
});
test("host GPU alone does not imply Docker can use it", () => {
  assert.equal(recommendedSelection({...ready,gpu_runtime:false},gpu).accelerator,"cpu");
  assert.equal(recommendedSelection({...ready,status:"unavailable"},gpu).accelerator,"cpu");
});
test("missing or malformed measurements do not imply free memory", () => {
  for(const bad of [{}, {...gpu,memory_used_mib:undefined}, {...gpu,memory_used_mib:-1}, {...gpu,memory_used_mib:NaN}]) {
    assert.equal(recommendedSelection(ready,bad).accelerator,"cpu");
  }
});
test("a recommendation does not mutate the supplied observations", () => {
  const snapshot=JSON.stringify({ready,gpu});
  recommendedSelection(ready,gpu);
  assert.equal(JSON.stringify({ready,gpu}),snapshot);
});
