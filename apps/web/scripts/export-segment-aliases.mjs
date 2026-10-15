// After `next build` with output: "export" (recorded-only site): Next.js 16 writes per-segment
// prefetch files nested (bench/__next.bench/__PAGE__.txt), while its client router requests them
// dot-joined (bench/__next.bench.__PAGE__.txt). A static host then answers 404 and every link
// falls back to a full page load. Write each nested file also under the requested name.
import { copyFileSync, existsSync, readdirSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";

const OUT = new URL("../out/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
if (!existsSync(OUT)) {
  console.error("out/ not found: run `NEXT_PUBLIC_RECORDED_ONLY=true pnpm build` first");
  process.exit(1);
}

let n = 0;
function walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) {
      if (name !== "_next") walk(p);
      continue;
    }
    if (!name.endsWith(".txt")) continue;
    const parts = relative(OUT, p).split(sep);
    const i = parts.findIndex((s) => s.startsWith("__next."));
    if (i < 0 || i === parts.length - 1) continue; // already flat
    const alias = join(OUT, ...parts.slice(0, i), parts.slice(i).join("."));
    copyFileSync(p, alias);
    n += 1;
  }
}
walk(OUT);
console.log(`segment aliases written: ${n}`);
