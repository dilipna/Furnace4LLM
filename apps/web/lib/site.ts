// A recorded-only deployment (NEXT_PUBLIC_RECORDED_ONLY=true): a static export (next.config.ts,
// `out/`) hosted anywhere static files are served, with no API service. Evidence pages read the
// build-time snapshot of the bench results (lib/bench-snapshot.json,
// scripts/export_bench_snapshot.py), and every live control says it is unavailable here instead
// of calling an API that does not exist.
// The browser-only /prefix-check tool is independent of this flag and never calls an API.
export const RECORDED_ONLY = process.env.NEXT_PUBLIC_RECORDED_ONLY === "true";

/** A committed result file on GitHub (recorded-only links where the live site has a query route). */
export const REPO_BLOB = "https://github.com/dilipna/Furnace4LLM/blob/main";
