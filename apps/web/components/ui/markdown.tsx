import type { ReactNode } from "react";

/** Inline markdown: **bold**, `code`. Builds React nodes (never raw HTML). */
function inline(text: string, keyBase: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let n = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const tok = m[0];
    out.push(
      tok.startsWith("**") ? (
        <strong key={`${keyBase}-${n++}`} className="font-semibold text-fg-0">
          {tok.slice(2, -2)}
        </strong>
      ) : (
        <code key={`${keyBase}-${n++}`} className="num rounded-[3px] bg-bg-2 px-1 text-[0.95em] text-fg-1">
          {tok.slice(1, -1)}
        </code>
      ),
    );
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

const cells = (row: string) =>
  row
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((c) => c.trim());

/** Block markdown subset used by FurnaceBench reports: headings, tables, bullet lists, paragraphs. */
export function Markdown({ source }: { source: string }) {
  const lines = source.split(/\r?\n/);
  const blocks: ReactNode[] = [];
  let i = 0;
  let k = 0;
  while (i < lines.length) {
    const line = lines[i];
    const key = `b${k++}`;
    if (!line.trim()) {
      i++;
      continue;
    }
    const h = /^(#{1,4})\s+(.*)$/.exec(line);
    if (h) {
      const level = h[1].length;
      const cls =
        level === 1
          ? "mt-2 font-display text-[24px] font-semibold tracking-[-0.02em] text-fg-0"
          : level === 2
            ? "mt-10 border-t border-line pt-6 text-[17px] font-medium text-fg-0"
            : "mt-6 text-[14px] font-medium text-fg-0";
      blocks.push(
        <div key={key} role="heading" aria-level={level} className={cls}>
          {inline(h[2], key)}
        </div>,
      );
      i++;
      continue;
    }
    if (line.trim().startsWith("|") && lines[i + 1]?.trim().match(/^\|[\s:|-]+\|?$/)) {
      const head = cells(line);
      const align = cells(lines[i + 1]).map((c) => (c.endsWith(":") ? "text-right" : "text-left"));
      const rows: string[][] = [];
      i += 2;
      while (i < lines.length && lines[i].trim().startsWith("|")) rows.push(cells(lines[i++]));
      blocks.push(
        <div key={key} className="mt-3 overflow-x-auto">
          <table className="w-full border-collapse text-[12px] [overflow-wrap:normal]">
            <thead>
              <tr className="border-b border-line text-fg-3">
                {head.map((c, j) => (
                  <th key={j} className={`py-2 pr-4 font-normal ${align[j] ?? "text-left"}`}>
                    {inline(c, `${key}h${j}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, ri) => (
                <tr key={ri} className="border-b border-line align-top">
                  {r.map((c, j) => (
                    <td key={j} className={`num py-1.5 pr-4 text-fg-1 ${align[j] ?? "text-left"}`}>
                      {inline(c, `${key}r${ri}c${j}`)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }
    if (/^\s*[-*]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) items.push(lines[i++].replace(/^\s*[-*]\s+/, ""));
      blocks.push(
        <ul key={key} className="mt-3 list-disc space-y-1.5 pl-5 text-[13px] text-fg-1 marker:text-fg-3">
          {items.map((t, j) => (
            <li key={j}>{inline(t, `${key}l${j}`)}</li>
          ))}
        </ul>,
      );
      continue;
    }
    const para: string[] = [lines[i++]]; // always consume one line, so every branch makes progress
    while (i < lines.length && lines[i].trim() && !/^(#{1,4}\s|\||\s*[-*]\s)/.test(lines[i])) para.push(lines[i++]);
    blocks.push(
      <p key={key} className="mt-3 text-[13px] leading-relaxed text-fg-1">
        {inline(para.join(" "), key)}
      </p>,
    );
  }
  // Long paths and keys must wrap instead of widening the page; tables scroll instead.
  return <div className="[overflow-wrap:anywhere]">{blocks}</div>;
}
