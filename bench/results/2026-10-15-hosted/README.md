# Recorded-only site on Cloudflare Pages Free, 2026-10-15

Public URL: **https://furnace-5h6.pages.dev** (production branch `main`; `furnace.pages.dev` was
taken, so Cloudflare added the suffix). Deployed commit **08868cf**, built from a clean
`git archive` of that commit (`NEXT_PUBLIC_RECORDED_ONLY=true pnpm build:static`, 193 files,
24 MB) and uploaded with `wrangler pages deploy` (deployment 7c68fec9). Account: "Ubdg0312@gmail.com's
Account" (Cloudflare, standard). Services in use: one Pages project (direct upload, no Git
source, no build settings, no Functions, no custom domain); Wrangler's OAuth grant was limited
to account read, user read and Pages write. Nothing paid; no payment method was needed.

Verified with the laptop's API, runner, vLLM, Postgres and local preview all stopped:

- `scripts/smoke_hosted.py --web` (`smoke-web.md`): **18 of 20 passed**. Pages render their
  recorded evidence and recorded-only notices; `/pricing` 302 → `/pilot#terms-h`; LinkedIn
  contact link; poster and recorded lab telemetry; `/api/*` and `/healthz` 404/405; unknown pages
  404. The two failures are the recordings' byte-range responses (below).
- Browser pass (Playwright Chromium, desktop 1440 px and iPhone 13 emulation, 8 pages): no failed
  requests, no console errors, no `/api` calls, no horizontal overflow; the WebM played (4 s,
  readyState 4) on both; header links, the hero call to action, `/pricing` and the contact link
  resolved. iPhone emulation is Chromium at a phone viewport, not Safari.

**Open limitation: video byte ranges.** Cloudflare Pages answers `Range` requests for the
recordings with 200 and the full file (no `Accept-Ranges`, no 206). Chromium and Firefox play
it; WebKit (Safari on iOS and macOS) requires a 206 with `Content-Range` for media, so the
recording may not play there. Not tested on a real iPhone.

Cloudflare blocks Python's default `Python-urllib` User-Agent (403); the smoke test now sends
`furnace-smoke/1.0`. Browsers are unaffected.
