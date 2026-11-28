import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

export type EverydayRecording = {
  kind: "private-document-recording";
  source_commit: string;
  model: string;
  accelerator: "cpu" | "nvidia";
  files: Record<string, {sha256: string; bytes: number}>;
};

/** Only executed, locally staged media can become the public-facing recorded demo. */
export function readEverydayRecording(): EverydayRecording | null {
  const root = join(process.cwd(), "public/product/generated/everyday");
  if (!existsSync(join(root, "manifest.json"))) return null;
  const data: EverydayRecording = JSON.parse(readFileSync(join(root,"manifest.json"),"utf8"));
  if(data.kind !== "private-document-recording" || !/^[a-f0-9]{40}$/.test(data.source_commit)) throw new Error("Not an executed document recording");
  for(const name of ["journey.webm","home.png","document.png","answer.png","receipt.png","record.json","captions.vtt"]) {
    const bytes=readFileSync(join(root,name));
    const expected=data.files[name];
    if(!expected || bytes.byteLength!==expected.bytes || createHash("sha256").update(bytes).digest("hex")!==expected.sha256) throw new Error("Document recording bytes differ from evidence: "+name);
  }
  return data;
}
