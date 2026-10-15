import type { NextConfig } from "next";

// All browser traffic goes to /api on the web origin and is rewritten to FastAPI,
// so session cookies stay first-party when web (Vercel) and API (Render) are on
// different hosts. A recorded-only deployment (lib/site.ts) has no API: /api/* is not routed.
const API_URL = process.env.FURNACE_API_URL ?? "http://localhost:8010";
const RECORDED_ONLY = process.env.NEXT_PUBLIC_RECORDED_ONLY === "true";

// Recorded-only builds are a static export (`out/`, any static host, e.g. Cloudflare Pages):
// no server, so no rewrites and no image optimization (the app uses no next/image).
const nextConfig: NextConfig = RECORDED_ONLY
  ? { output: "export", images: { unoptimized: true } }
  : {
      async rewrites() {
        return [
          { source: "/api/:path*", destination: `${API_URL}/api/:path*` },
          { source: "/healthz", destination: `${API_URL}/healthz` },
        ];
      },
    };

export default nextConfig;
