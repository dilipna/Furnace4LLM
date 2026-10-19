/** Browser-safe structural replay. No I/O, persistence, or model calls. */
type Message = { role: string; content: string };
type Snapshot = { messages: Message[]; question: string }[];
export const MAX_BYTES = 2 * 1024 * 1024;

function parse(text: string, label: string): Snapshot {
  if (new TextEncoder().encode(text).length > MAX_BYTES) throw new Error(`${label}: limit is 2 MiB per snapshot.`);
  const lines = text.trim().split(/\r?\n/);
  if (!text.trim() || lines.length < 2 || lines.length > 200) throw new Error(`${label}: provide 2–200 JSONL rows, one request per line.`);
  const rows = lines.map((line, index) => {
    let value;
    try { value = JSON.parse(line); } catch { throw new Error(`${label}, line ${index + 1}: invalid JSON.`); }
    const messages = value?.messages;
    if (!Array.isArray(messages) || !messages.length || messages.some(m => !m || typeof m.role !== "string" || !m.role || typeof m.content !== "string")) {
      throw new Error(`${label}, line ${index + 1}: expected a nonempty messages array with text role/content fields. Multimodal content is unsupported.`);
    }
    const last = messages[messages.length - 1];
    if (last.role !== "user" || !last.content.trim()) throw new Error(`${label}, line ${index + 1}: end with a nonempty user question.`);
    return { messages: messages as Message[], question: last.content as string };
  });
  if (new Set(rows.map(r => r.question)).size !== rows.length) throw new Error(`${label}: use distinct final user questions; duplicates are ambiguous.`);
  return rows;
}

function shared(rows: Snapshot): number {
  const render = (messages: Message[]) => Array.from(messages.map(m => `${m.role}\n${m.content}\n`).join(""));
  const first = render(rows[0].messages);
  let limit = first.length;
  for (const row of rows.slice(1)) {
    const next = render(row.messages);
    let i = 0;
    while (i < limit && i < next.length && first[i] === next[i]) i++;
    limit = i;
  }
  return limit;
}

export function checkPrefix(baseText: string, headText: string) {
  const base = parse(baseText, "Base"), head = parse(headText, "Head");
  if (base.length !== head.length || base.some((r, i) => r.question !== head[i].question)) throw new Error("Base and head need identical final user questions in identical order.");
  const baseShared = shared(base), headShared = shared(head);
  const required = Math.floor(baseShared * 0.9);
  const meaningful = required > Array.from(base[0].messages[0].role).length + 1;
  return { status: !meaningful ? "INCONCLUSIVE" : headShared >= required ? "PASS" : "FAIL", baseShared, headShared, required, requests: base.length };
}

export function exampleSnapshots(fixed: boolean) {
  const stable = "You are an operations assistant. Use this runbook: check service health, inspect error logs, verify dependencies, and propose a reversible recovery step. Never invent a successful recovery.\n";
  const questions = ["Why is the service slow?", "How do I investigate errors?", "What should I check before restarting?"];
  const snapshot = (head: boolean) => questions.map((question, i) => JSON.stringify({ messages: [
    { role: "system", content: head ? fixed ? `${stable}Request: ${i}` : `Request: ${i}\n${stable}` : stable },
    { role: "user", content: question },
  ] })).join("\n");
  return { base: snapshot(false), head: snapshot(true) };
}
