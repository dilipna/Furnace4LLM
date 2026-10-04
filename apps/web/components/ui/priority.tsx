const STYLE = {
  P0: "bg-ember-lo text-ember-hi border-ember/40",
  P1: "text-fg-1 border-line-strong",
  P2: "text-fg-3 border-line",
} as const;

export function PriorityTag({ p }: { p: "P0" | "P1" | "P2" }) {
  return (
    <span className={`num inline-flex h-5 w-8 shrink-0 items-center justify-center rounded-ctl border text-[11px] ${STYLE[p]}`}>
      {p}
    </span>
  );
}
