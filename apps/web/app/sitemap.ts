import type { MetadataRoute } from "next";
export const dynamic = "force-static";
export default function sitemap(): MetadataRoute.Sitemap { const base = process.env.NEXT_PUBLIC_SITE_URL ?? "https://furnace-5h6.pages.dev"; return ["", "/start", "/demo", "/docs", "/security", "/pricing", "/releases", "/faq", "/support", "/about", "/privacy", "/terms", "/earlier-work"].map(path => ({ url: base + path })); }
