import type { NextConfig } from "next";

// All browser traffic goes to /api on the web origin and is rewritten to FastAPI,
// so session cookies stay first-party when web (Vercel) and API (Render) are on
// different hosts.
const API_URL = process.env.FURNACE_API_URL ?? "http://localhost:8010";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${API_URL}/api/:path*` },
      { source: "/healthz", destination: `${API_URL}/healthz` },
    ];
  },
};

export default nextConfig;
