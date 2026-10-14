import type { NextConfig } from "next";

// All browser traffic goes to /api on the web origin and is rewritten to FastAPI,
// so session cookies stay first-party when web (Vercel) and API (Render) are on
// different hosts. A recorded-only deployment (lib/site.ts) has no API: /api/* is not routed.
const API_URL = process.env.FURNACE_API_URL ?? "http://localhost:8010";
const RECORDED_ONLY = process.env.NEXT_PUBLIC_RECORDED_ONLY === "true";

const nextConfig: NextConfig = {
  async rewrites() {
    if (RECORDED_ONLY) return [];
    return [
      { source: "/api/:path*", destination: `${API_URL}/api/:path*` },
      { source: "/healthz", destination: `${API_URL}/healthz` },
    ];
  },
};

export default nextConfig;
