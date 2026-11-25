import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { createHash } from "node:crypto";
import { validInstaller, type Installer } from "./download";

/** A button is enabled only when the locally staged binary matches its build metadata. */
export function readInstaller(): Installer | null {
  const root = join(process.cwd(), "public", "downloads");
  const metadata = join(root, "installer.json");
  if (!existsSync(metadata)) return null;
  const value: unknown = JSON.parse(readFileSync(metadata, "utf8"));
  if (!validInstaller(value)) throw new Error("Invalid installer metadata");
  if (value.download_url) return value;
  if (process.env.FURNACE_PUBLIC_SITE === "true") throw new Error("Stage an approved public release link before deploying; local installers exceed Pages limits");
  const binary = readFileSync(join(root, value.file));
  if (binary.byteLength !== value.bytes || createHash("sha256").update(binary).digest("hex") !== value.sha256) throw new Error("Installer bytes differ from build metadata");
  return value;
}

export function readReleaseNotes(): { tag_name: string; name: string; published_at: string; html_url: string; body: string }[] {
  const file = join(process.cwd(), "public/downloads/releases.json");
  if (!existsSync(file)) return [];
  const data = JSON.parse(readFileSync(file, "utf8"));
  return data.releases.filter((item: { html_url: string }) => item.html_url.startsWith("https://github.com/dilipna/Furnace4LLM/releases/"));
}
