import test from "node:test";
import assert from "node:assert/strict";
import { platformFor, validInstaller } from "./download.ts";

test("download target distinguishes desktop and mobile without disguising unsupported platforms", () => {
  for (const [agent, expected] of [["Windows NT 10.0", "windows"], ["Macintosh; Intel Mac OS X", "macos"], ["X11; Linux x86_64", "linux"], ["Linux; Android 14", "other"], ["iPhone; Mac OS X", "other"], ["", "other"]]) assert.equal(platformFor(agent), expected);
});
test("installer metadata must identify real bounded bytes, source and a safe file name", () => {
  const data = {version: "0.1.0", commit: "a".repeat(40), built_at: "2026-11-23T00:00:00Z", file: "Furnace-0.1.0-aaaaaaaaaaaa-windows-x64.exe", bytes: 100, sha256: "b".repeat(64), signed: false};
  assert.ok(validInstaller(data));
  for (const patch of [{file: "../evil.exe"}, {file: "https://evil.test/a.exe"}, {sha256: "invalid"}, {bytes: 0}, {bytes: Infinity}, {bytes: 1.2}, {built_at: "not a date"}, {signed: "yes"}, {commit: "unknown"}]) assert.equal(validInstaller({...data, ...patch}), false);
});
