/** FURNACE wordmark with the ember "throat" mark: a small slotted square. */
export function Wordmark({ size = 13 }: { size?: number }) {
  return (
    <span className="inline-flex items-center gap-2.5 select-none" aria-label="Furnace">
      <svg width={size + 3} height={size + 3} viewBox="0 0 16 16" aria-hidden="true">
        <rect x="0.5" y="0.5" width="15" height="15" rx="2" fill="none" stroke="var(--line-strong)" />
        <rect x="4" y="9" width="8" height="3" rx="0.5" fill="var(--ember)" />
        <rect x="4" y="5" width="8" height="1.5" rx="0.5" fill="var(--fg-3)" />
      </svg>
      <span className="wordmark text-fg-0" style={{ fontSize: size }}>
        Furnace
      </span>
    </span>
  );
}
