"use client";

import { useId, useMemo, useState } from "react";

export type Point = { y: number | null; lo?: number | null; hi?: number | null };
export type Series = { id: string; label: string; color: string; points: Point[] };

type Props = {
  title: string;
  subtitle?: string;
  xs: number[]; // categorical x positions (e.g. concurrency levels), evenly spaced
  xLabel: string;
  series: Series[];
  format: (v: number) => string;
  rangeNote?: string; // what the shaded band means
};

const W = 640;
const H = 260;
const M = { top: 12, right: 64, bottom: 36, left: 56 };

function niceMax(v: number): number {
  if (v <= 0) return 1;
  const p = 10 ** Math.floor(Math.log10(v));
  for (const m of [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]) if (m * p >= v) return m * p;
  return 10 * p;
}

/**
 * Line chart for a handful of series over categorical x (concurrency levels).
 * Spec: 2px lines, >= 8px end markers with a 2px surface ring, min-max band as a 10% wash,
 * hairline grid, crosshair + one tooltip for every series, keyboard focus moves the crosshair.
 */
export function LineChart({ title, subtitle, xs, xLabel, series, format, rangeNote }: Props) {
  const [hover, setHover] = useState<number | null>(null);
  const id = useId();
  const pw = W - M.left - M.right;
  const ph = H - M.top - M.bottom;

  const yMax = useMemo(() => {
    const vals = series.flatMap((s) => s.points.flatMap((p) => [p.y, p.hi]).filter((v): v is number => v != null));
    return niceMax(Math.max(0, ...vals));
  }, [series]);

  const x = (i: number) => M.left + (xs.length === 1 ? pw / 2 : (i * pw) / (xs.length - 1));
  const y = (v: number) => M.top + ph - (v / yMax) * ph;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => t * yMax);

  const path = (pts: Point[]) =>
    pts
      .map((p, i) => (p.y == null ? null : `${x(i)},${y(p.y)}`))
      .filter(Boolean)
      .map((c, i) => `${i === 0 ? "M" : "L"}${c}`)
      .join("");
  const band = (pts: Point[]) => {
    const ok = pts.map((p, i) => ({ ...p, i })).filter((p) => p.lo != null && p.hi != null);
    if (ok.length < 2) return "";
    const top = ok.map((p) => `${x(p.i)},${y(p.hi as number)}`);
    const bot = ok.reverse().map((p) => `${x(p.i)},${y(p.lo as number)}`);
    return `M${top.join("L")}L${bot.join("L")}Z`;
  };

  function onMove(e: React.PointerEvent<SVGRectElement>) {
    const r = e.currentTarget.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * pw;
    const i = xs.length === 1 ? 0 : Math.round((px / pw) * (xs.length - 1));
    setHover(Math.max(0, Math.min(xs.length - 1, i)));
  }
  function onKey(e: React.KeyboardEvent) {
    if (e.key === "ArrowRight") setHover((h) => Math.min(xs.length - 1, (h ?? -1) + 1));
    else if (e.key === "ArrowLeft") setHover((h) => Math.max(0, (h ?? xs.length) - 1));
    else if (e.key === "Escape") setHover(null);
  }

  // Direct end labels only when they do not collide (legend always carries identity).
  const ends = series.map((s) => {
    const last = [...s.points].reverse().find((p) => p.y != null);
    return last?.y != null ? y(last.y) : null;
  });
  const directLabels = ends.every((a, i) => a != null && ends.every((b, j) => i === j || b == null || Math.abs(a - b) > 14));

  return (
    <figure className="min-w-0">
      <figcaption className="mb-2 flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <div>
          <div className="text-[13px] font-medium text-fg-0">{title}</div>
          {subtitle && <div className="text-[12px] text-fg-3">{subtitle}</div>}
        </div>
        <ul className="flex gap-4 text-[12px] text-fg-1" aria-label="Legend">
          {series.map((s) => (
            <li key={s.id} className="flex items-center gap-1.5">
              <svg width="14" height="8" aria-hidden="true">
                <line x1="0" y1="4" x2="14" y2="4" stroke={s.color} strokeWidth="2" strokeLinecap="round" />
              </svg>
              {s.label}
            </li>
          ))}
        </ul>
      </figcaption>
      <div
        className="relative rounded-[6px] border border-line bg-bg-1 outline-none"
        tabIndex={0}
        role="group"
        aria-label={`${title}. Use left and right arrows to read values.`}
        aria-describedby={`${id}-tip`}
        onKeyDown={onKey}
        onBlur={() => setHover(null)}
      >
        <svg viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full" role="img" aria-hidden="true">
          {ticks.map((t) => (
            <g key={t}>
              <line x1={M.left} x2={W - M.right} y1={y(t)} y2={y(t)} stroke="var(--viz-grid)" strokeWidth="1" />
              <text x={M.left - 8} y={y(t) + 4} textAnchor="end" className="num" fontSize="11" fill="var(--fg-3)">
                {format(t)}
              </text>
            </g>
          ))}
          {xs.map((v, i) => (
            <text key={v} x={x(i)} y={H - M.bottom + 18} textAnchor="middle" className="num" fontSize="11" fill="var(--fg-3)">
              {v}
            </text>
          ))}
          <text x={M.left + pw / 2} y={H - 4} textAnchor="middle" fontSize="11" fill="var(--fg-3)">
            {xLabel}
          </text>
          {series.map((s) => (
            <path key={`b-${s.id}`} d={band(s.points)} fill={s.color} opacity="0.1" />
          ))}
          {series.map((s) => (
            <path key={`l-${s.id}`} d={path(s.points)} fill="none" stroke={s.color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
          ))}
          {hover != null && (
            <line x1={x(hover)} x2={x(hover)} y1={M.top} y2={M.top + ph} stroke="var(--line-strong)" strokeWidth="1" />
          )}
          {series.map((s) =>
            s.points.map((p, i) =>
              p.y == null ? null : (
                <circle key={`m-${s.id}-${xs[i]}`} cx={x(i)} cy={y(p.y)} r={hover === i ? 5 : 4} fill={s.color} stroke="var(--bg-1)" strokeWidth="2" />
              ),
            ),
          )}
          {directLabels &&
            series.map((s, k) =>
              ends[k] == null ? null : (
                <text key={`d-${s.id}`} x={x(xs.length - 1) + 10} y={(ends[k] as number) + 4} fontSize="11" fill="var(--fg-1)">
                  {s.label}
                </text>
              ),
            )}
          <rect
            x={M.left - 12}
            y={M.top}
            width={pw + 24}
            height={ph}
            fill="transparent"
            onPointerMove={onMove}
            onPointerLeave={() => setHover(null)}
          />
        </svg>
        <div id={`${id}-tip`} role="status" aria-live="polite" className="sr-only">
          {hover != null &&
            `${xLabel} ${xs[hover]}: ` +
              series.map((s) => `${s.label} ${s.points[hover]?.y == null ? "no data" : format(s.points[hover].y as number)}`).join("; ")}
        </div>
        {hover != null && (
          <div
            className="pointer-events-none absolute top-2 z-10 min-w-[170px] rounded-[3px] border border-line-strong bg-bg-2 px-3 py-2 text-[12px]"
            style={{
              left: `${(x(hover) / W) * 100}%`,
              transform: hover > (xs.length - 1) / 2 ? "translateX(calc(-100% - 12px))" : "translateX(12px)",
            }}
          >
            <div className="text-fg-3">
              {xLabel} <span className="num text-fg-1">{xs[hover]}</span>
            </div>
            {series.map((s) => {
              const p = s.points[hover];
              return (
                <div key={s.id} className="mt-1 flex items-center gap-2">
                  <svg width="10" height="6" aria-hidden="true">
                    <line x1="0" y1="3" x2="10" y2="3" stroke={s.color} strokeWidth="2" />
                  </svg>
                  <span className="num font-medium text-fg-0">{p?.y == null ? "–" : format(p.y)}</span>
                  {p?.lo != null && p?.hi != null && (
                    <span className="num text-fg-3">
                      [{format(p.lo)}–{format(p.hi)}]
                    </span>
                  )}
                  <span className="ml-auto pl-3 text-fg-2">{s.label}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
      {rangeNote && <p className="mt-1.5 text-[11px] text-fg-3">{rangeNote}</p>}
    </figure>
  );
}
