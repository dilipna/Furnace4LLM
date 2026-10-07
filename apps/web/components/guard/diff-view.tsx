/** Unified diff, line by line. Additions and removals keep their +/- prefix as the primary cue. */
export function DiffView({ patch, maxLines = 400 }: { patch: string; maxLines?: number }) {
  const lines = patch.split("\n");
  const shown = lines.slice(0, maxLines);
  return (
    <div className="overflow-x-auto rounded-[6px] border border-line bg-bg-1">
      <pre className="num min-w-max py-2 text-[12px] leading-[1.6]">
        {shown.map((l, i) => {
          const cls = l.startsWith("+++") || l.startsWith("---")
            ? "text-fg-1 font-medium"
            : l.startsWith("@@")
              ? "text-fg-3"
              : l.startsWith("+")
                ? "bg-ok/10 text-fg-0"
                : l.startsWith("-")
                  ? "bg-bad/10 text-fg-1"
                  : "text-fg-2";
          return (
            <div key={i} className={`px-4 ${cls}`}>
              {l || " "}
            </div>
          );
        })}
        {lines.length > maxLines && <div className="px-4 text-fg-3">… {lines.length - maxLines} more lines</div>}
      </pre>
    </div>
  );
}
