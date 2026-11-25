import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
export type Recording = { source_commit: string; video: string; bytes: number; sha256: string; rule_passed: number; rule_total: number; compared: number; identical: number; image_sizes: Record<string, number[]> };
export function readRecording(): Recording | null {
  const root = join(process.cwd(), "public/product/generated");
  if (!existsSync(join(root, "manifest.json"))) return null;
  const data: Recording = JSON.parse(readFileSync(join(root, "manifest.json"), "utf8"));
  if (data.video !== "studio-journey.webm") throw new Error("Unexpected local recording file");
  const bytes = readFileSync(join(root, data.video));
  if (bytes.byteLength !== data.bytes || createHash("sha256").update(bytes).digest("hex") !== data.sha256) throw new Error("Recording bytes differ from executed evidence");
  return data;
}
