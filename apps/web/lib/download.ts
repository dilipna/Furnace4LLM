export type Installer = { experience?: string; version: string; commit: string; built_at: string; file: string; bytes: number; sha256: string; signed: boolean; download_url?: string; published?: boolean; published_at?: string };
export function platformFor(userAgent: string): "windows" | "macos" | "linux" | "other" {
  if (/Android|iPhone|iPad/i.test(userAgent)) return "other";
  if (/Windows/i.test(userAgent)) return "windows";
  if (/Macintosh|Mac OS/i.test(userAgent)) return "macos";
  if (/Linux/i.test(userAgent)) return "linux";
  return "other";
}
export function validInstaller(value: unknown): value is Installer {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  if (v.download_url !== undefined) {
    try {
      const url = new URL(String(v.download_url));
      if (url.origin !== "https://github.com" || url.username || url.password || url.search || url.hash || !url.pathname.startsWith("/dilipna/Furnace4LLM/releases/download/") || url.pathname.split("/").length !== 7 || decodeURIComponent(url.pathname.split("/").at(-1) ?? "") !== v.file || v.published !== true || typeof v.published_at !== "string" || !Number.isFinite(Date.parse(v.published_at))) return false;
    } catch { return false; }
  }
  return typeof v.version === "string" && typeof v.commit === "string" && /^[a-f0-9]{40}$/.test(v.commit)
    && typeof v.built_at === "string" && Number.isFinite(Date.parse(v.built_at))
    && typeof v.file === "string" && /^Furnace-[\w.+-]+-windows-x64\.exe$/.test(v.file)
    && typeof v.bytes === "number" && Number.isSafeInteger(v.bytes) && v.bytes > 0
    && typeof v.sha256 === "string" && /^[a-f0-9]{64}$/.test(v.sha256) && typeof v.signed === "boolean";
}
