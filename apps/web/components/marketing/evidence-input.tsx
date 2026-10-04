"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";

type Mode = "github" | "url" | "upload";

const MODES: { id: Mode; label: string; hint: string; placeholder: string }[] = [
  {
    id: "github",
    label: "GitHub repo",
    hint: "Public repos scan without an account. Read-only.",
    placeholder: "github.com/acme/support-bot",
  },
  {
    id: "url",
    label: "App URL",
    hint: "Furnace inspects the page and its network calls. No logins, GET only.",
    placeholder: "https://support.acme.dev",
  },
  {
    id: "upload",
    label: "Upload",
    hint: "Source ZIP, README, screenshots, diagrams, JSONL traces.",
    placeholder: "",
  },
];

export function EvidenceInput() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("github");
  const [value, setValue] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const active = MODES.find((m) => m.id === mode)!;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      let res: Response;
      if (mode === "upload") {
        const body = new FormData();
        files.forEach((f) => body.append("files", f));
        res = await fetch("/api/public/scans/upload", { method: "POST", body });
      } else {
        res = await fetch("/api/public/scans", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ kind: mode, value: value.trim() }),
        });
      }
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        throw new Error(detail?.detail ?? `Scan request failed (${res.status})`);
      }
      const { scan_id } = (await res.json()) as { scan_id: string };
      router.push(`/scans/${scan_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scan request failed");
      setBusy(false);
    }
  }

  const ready = mode === "upload" ? files.length > 0 : value.trim().length > 3;

  return (
    <form onSubmit={submit} className="w-full max-w-[640px]">
      <div role="tablist" aria-label="Evidence source" className="flex gap-px border-b border-line">
        {MODES.map((m) => (
          <button
            key={m.id}
            type="button"
            role="tab"
            aria-selected={mode === m.id}
            onClick={() => {
              setMode(m.id);
              setError(null);
            }}
            className={`-mb-px border-b px-3 pb-2 text-[13px] transition-colors duration-150 ${
              mode === m.id ? "border-ember text-fg-0" : "border-transparent text-fg-2 hover:text-fg-1"
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      <div className="mt-3 flex gap-2">
        {mode === "upload" ? (
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            className="flex h-10 flex-1 items-center rounded-ctl border border-dashed border-line-strong bg-bg-1 px-3 text-left text-fg-2 hover:border-fg-3"
          >
            {files.length ? (
              <span className="num truncate text-fg-1">
                {files.map((f) => f.name).join(", ")}
              </span>
            ) : (
              "Choose files…"
            )}
            <input
              ref={fileRef}
              type="file"
              multiple
              className="hidden"
              accept=".zip,.md,.txt,.png,.jpg,.jpeg,.webp,.jsonl,.json,.yaml,.yml"
              onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
            />
          </button>
        ) : (
          <input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={active.placeholder}
            spellCheck={false}
            autoComplete="off"
            className="num h-10 flex-1 rounded-ctl border border-line-strong bg-bg-1 px-3 text-[13px] text-fg-0 placeholder:text-fg-3 hover:border-fg-3 focus:border-fg-2 focus:outline-none"
          />
        )}
        <Button type="submit" variant="primary" disabled={!ready || busy} className="h-10 px-4">
          {busy ? "Starting scan…" : "Scan"}
        </Button>
      </div>
      <p className="mt-2 text-[12px] text-fg-3">{active.hint}</p>
      {error && (
        <p role="alert" className="mt-2 text-[12px] text-bad">
          {error}
        </p>
      )}
    </form>
  );
}
