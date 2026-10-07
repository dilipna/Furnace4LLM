"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type Item = {
  id: string;
  model: string;
  kind: string;
  question: string;
  retrieved_ids: string[];
  context: string;
  answer: string;
  gold_answer: string | null;
};
type Label = { id: string; grounded: boolean; correct: boolean | null; notes: string };
type Queue = { items: Item[]; labels: Record<string, Label>; writable: boolean };

/**
 * Keyboard-driven labeling (j/k move, p/f grounded pass/fail, c/x/- correct yes/no/n.a.,
 * n focuses the note). Every change is saved immediately; the server keeps one label per item.
 */
export function LabelQueue() {
  const [q, setQ] = useState<Queue | null>(null);
  const [i, setI] = useState(0);
  const [drafts, setDrafts] = useState<Record<string, Partial<Label>>>({});
  const [status, setStatus] = useState<string>("");
  const noteRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    fetch("/api/labels/queue")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data: Queue) => {
        setQ(data);
        const first = data.items.findIndex((it) => !data.labels[it.id]);
        setI(first >= 0 ? first : 0);
      })
      .catch((e: Error) => setStatus(`Could not load the queue: ${e.message}`));
  }, []);

  const item = q?.items[i];
  const saved = item ? q?.labels[item.id] : undefined;
  const current: Partial<Label> = { ...saved, ...(item ? drafts[item.id] : {}) };

  const save = useCallback(
    async (patch: Partial<Label>) => {
      if (!item || !q) return;
      const next = { ...q.labels[item.id], ...drafts[item.id], ...patch };
      setDrafts((d) => ({ ...d, [item.id]: next }));
      if (next.grounded == null) {
        setStatus("Mark grounded (p/f) to save.");
        return;
      }
      if (!q.writable) {
        setStatus("Labeling is disabled on this deployment.");
        return;
      }
      setStatus("Saving…");
      const body = { id: item.id, grounded: next.grounded, correct: next.correct ?? null, notes: next.notes ?? "" };
      const r = await fetch("/api/labels", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
      if (!r.ok) {
        setStatus(`Save failed (HTTP ${r.status}).`);
        return;
      }
      const rec = (await r.json()) as Label;
      setQ({ ...q, labels: { ...q.labels, [item.id]: rec } });
      setStatus("Saved.");
    },
    [item, q, drafts],
  );

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.target instanceof HTMLTextAreaElement || e.metaKey || e.ctrlKey || e.altKey || !q) return;
      const k = e.key.toLowerCase();
      if (k === "j") setI((v) => Math.min(q.items.length - 1, v + 1));
      else if (k === "k") setI((v) => Math.max(0, v - 1));
      else if (k === "p") void save({ grounded: true });
      else if (k === "f") void save({ grounded: false });
      else if (k === "c") void save({ correct: true });
      else if (k === "x") void save({ correct: false });
      else if (k === "-") void save({ correct: null });
      else if (k === "n") {
        e.preventDefault();
        noteRef.current?.focus();
      } else return;
      e.preventDefault();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [q, save]);

  if (!q) return <p className="text-[13px] text-fg-2">{status || "Loading the labeling queue…"}</p>;
  if (!item) return <p className="text-[13px] text-fg-2">The queue is empty.</p>;
  const done = q.items.filter((it) => q.labels[it.id]).length;

  const choice = (on: boolean, label: string, key: string, onClick: () => void) => (
    <button
      onClick={onClick}
      aria-pressed={on}
      className={`rounded-[3px] border px-2.5 py-1 text-[12px] ${on ? "border-ember bg-ember-lo text-fg-0" : "border-line text-fg-2 hover:text-fg-0"}`}
    >
      {label} <span className="num ml-1 text-fg-3">{key}</span>
    </button>
  );

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="num text-[12px] text-fg-2">
          {done}/{q.items.length} labeled · item {i + 1} · <span className="text-fg-3">{item.id}</span>
        </div>
        <div className="h-1 w-48 overflow-hidden rounded-full bg-bg-3" aria-hidden="true">
          <div className="h-full bg-ember" style={{ width: `${(done / q.items.length) * 100}%` }} />
        </div>
      </div>

      <div className="mt-4 grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div>
          <div className="text-[11px] text-fg-3">
            {item.model} · {item.kind} · retrieved {item.retrieved_ids.join(", ") || "none"}
          </div>
          <p className="mt-1 text-[15px] text-fg-0">{item.question}</p>
          <div className="mt-4 text-[11px] text-fg-3">Model answer</div>
          <p className="mt-1 rounded-[6px] border border-line-strong bg-bg-2 p-3 text-[13px] text-fg-0">{item.answer || <em className="text-fg-3">(empty)</em>}</p>
          {item.gold_answer && (
            <>
              <div className="mt-4 text-[11px] text-fg-3">Documented answer</div>
              <p className="mt-1 text-[13px] text-fg-1">{item.gold_answer}</p>
            </>
          )}
          <div className="mt-5 flex flex-wrap items-center gap-2">
            <span className="w-[120px] text-[12px] text-fg-3">Grounded in context</span>
            {choice(current.grounded === true, "yes", "p", () => void save({ grounded: true }))}
            {choice(current.grounded === false, "no", "f", () => void save({ grounded: false }))}
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span className="w-[120px] text-[12px] text-fg-3">Correct answer</span>
            {choice(current.correct === true, "yes", "c", () => void save({ correct: true }))}
            {choice(current.correct === false, "no", "x", () => void save({ correct: false }))}
            {choice(current.correct === null && current.grounded != null, "n/a", "-", () => void save({ correct: null }))}
          </div>
          <label className="mt-3 block text-[12px] text-fg-3">
            Note <span className="num">(n)</span>
            <textarea
              ref={noteRef}
              defaultValue={saved?.notes ?? ""}
              key={item.id}
              rows={2}
              onBlur={(e) => {
                if (e.target.value !== (saved?.notes ?? "")) void save({ notes: e.target.value });
              }}
              onKeyDown={(e) => {
                if (e.key === "Escape") (e.target as HTMLTextAreaElement).blur();
              }}
              className="mt-1 block w-full rounded-[3px] border border-line bg-bg-1 p-2 text-[13px] text-fg-0"
            />
          </label>
          <div className="mt-3 flex items-center gap-3">
            <button onClick={() => setI((v) => Math.max(0, v - 1))} className="rounded-[3px] border border-line px-2.5 py-1 text-[12px] text-fg-2 hover:text-fg-0">
              ← prev <span className="num text-fg-3">k</span>
            </button>
            <button
              onClick={() => setI((v) => Math.min(q.items.length - 1, v + 1))}
              className="rounded-[3px] border border-line px-2.5 py-1 text-[12px] text-fg-2 hover:text-fg-0"
            >
              next <span className="num text-fg-3">j</span> →
            </button>
            <span role="status" aria-live="polite" className="text-[12px] text-fg-3">
              {status}
            </span>
          </div>
        </div>
        <div>
          <div className="text-[11px] text-fg-3">Context the model saw</div>
          <pre className="mt-1 max-h-[520px] overflow-auto rounded-[6px] border border-line bg-bg-1 p-3 font-sans text-[12px] whitespace-pre-wrap text-fg-1">
            {item.context}
          </pre>
        </div>
      </div>
    </div>
  );
}
