// node --test cloudflare/range.test.mjs  (pure parser cases; byte-level checks run against the deployed site
// in scripts/smoke_hosted.py)
import assert from "node:assert/strict";
import { test } from "node:test";
import { parseRange } from "./functions/demo/[file].js";

const S = 1000;

test("absent, other units, malformed and multi-range are ignored (200)", () => {
  for (const h of [null, "", "items=0-1", "bytes=", "bytes=-", "bytes=abc", "bytes=5-2", "bytes=0-1,5-9", "bytes=1-x"]) {
    assert.equal(parseRange(h, S), null, String(h));
  }
});

test("single ranges", () => {
  assert.deepEqual(parseRange("bytes=0-1", S), { start: 0, end: 1 });
  assert.deepEqual(parseRange("bytes=100-199", S), { start: 100, end: 199 });
  assert.deepEqual(parseRange("bytes=900-", S), { start: 900, end: 999 });
  assert.deepEqual(parseRange("bytes=0-", S), { start: 0, end: 999 });
  assert.deepEqual(parseRange("bytes=990-5000", S), { start: 990, end: 999 }); // end clamped
  assert.deepEqual(parseRange("bytes=999-999", S), { start: 999, end: 999 });
  assert.deepEqual(parseRange("BYTES = 3-4", S), { start: 3, end: 4 });
});

test("suffix ranges", () => {
  assert.deepEqual(parseRange("bytes=-100", S), { start: 900, end: 999 });
  assert.deepEqual(parseRange("bytes=-5000", S), { start: 0, end: 999 }); // longer than the file
});

test("unsatisfiable (416)", () => {
  assert.equal(parseRange("bytes=1000-", S), "unsatisfiable");
  assert.equal(parseRange("bytes=1000-2000", S), "unsatisfiable");
  assert.equal(parseRange("bytes=-0", S), "unsatisfiable");
});
