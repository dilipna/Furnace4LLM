// A recorded-only deployment (NEXT_PUBLIC_RECORDED_ONLY=true, e.g. the web app on Vercel with no
// API service): evidence pages read the build-time snapshot of the bench results
// (lib/bench-snapshot.json, scripts/export_bench_snapshot.py), and every live control says it is
// unavailable here instead of calling an API that does not exist.
export const RECORDED_ONLY = process.env.NEXT_PUBLIC_RECORDED_ONLY === "true";
