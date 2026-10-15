# Recorded-only site on Cloudflare Pages Free, 2026-10-15

Public URL: **https://furnace-5h6.pages.dev** (production branch `main`; `furnace.pages.dev` was
taken, so Cloudflare added the suffix). Deployed commit **fcdfb18** (production deployment
26bad82d, status success), built from `git archive` of that commit in a Linux container
(`NEXT_PUBLIC_RECORDED_ONLY=true pnpm build:static`, 170 files) and uploaded with
`wrangler pages deploy ../out` from `apps/web/cloudflare/`. Later commits change only this record
and docs.

Account and services: "redacted@example.invalid's Account" (Cloudflare, standard). One Pages project:
direct upload, no Git source, no build settings, only the free `furnace-5h6.pages.dev` domain, no
bindings (no KV, R2, D1 or other storage), compatibility date 2026-09-01. One Pages Function,
invoked only for `/demo/furnace-demo.webm` and `/demo/furnace-demo.mp4` (`_routes.json`), on the
free plan's daily request allowance; the project's `fail_open` is on, so if that allowance were
ever exhausted the recordings would be served as plain static files instead of erroring. No
paid plan, trial, payment method, domain, storage or Workers plan. Wrangler's OAuth grant:
account read, user read, Pages write.

All checks below ran with the laptop's API, runner, vLLM, Postgres and local preview stopped.

## Hosted smoke test (`smoke-web.md`): 46 of 46

- Every page (`/`, `/demo`, `/pilot`, `/bench`, `/guard`, `/guard/r1_dynamic_head`, `/lab`,
  `/evals`) answers 200 with its recorded evidence and recorded-only notices; `/pricing` 302 →
  `/pilot#terms-h`; LinkedIn contact link; poster; recorded lab telemetry; `/api/*` and
  `/healthz` 404/405; unknown pages 404.
- Byte ranges, for each recording, compared byte for byte with the committed files: full GET (200,
  SHA-256 equal, `Content-Length`, `Accept-Ranges: bytes`, correct `Content-Type`); `bytes=0-1`,
  `100-199`, `1000000-1000999`, `<size-10>-`, `-100` and `0-<2×size>` (clamped) each 206 with
  exactly those bytes, `Content-Range: bytes a-b/size` and `Content-Length: b-a+1`;
  `bytes=<size>-` 416 with `Content-Range: bytes */size`; multiple ranges, a malformed range and a
  stale `If-Range` each 200 with the whole file; HEAD with a range 206, headers only.
- `/demo`, `/demo/poster.png`, `/` and `/demo/__next._full.txt` carry no `x-furnace-range`
  header: they are static assets; the Function is not invoked for them.

On the b18a5f2 deployment, the first smoke run, seconds after deploying, had one miss (the WebM's
last 10 bytes came back as a 200 with the whole file and no Function marker); 90 repeated range
requests right after, the rerun and the final deployment's run all passed. Most likely that edge
location was still serving the previous, Function-less deployment; not proven.

## Browsers (Playwright on Windows; engines, not the branded browsers)

| engine | viewport | `/demo` player | page sweep (8 pages + 404) |
|---|---|---|---|
| Chromium 153 | 1440 px; 390 px mobile emulation | picks the MP4, plays (≈5 s), seek to 150 s lands at 153 s | 8 pages clean (no console errors, failed requests, `/api` calls or overflow), 404 page 404, client-side navigation works |
| WebKit 26.6 | 1440 px; iPhone 13 emulation | picks the MP4, plays (≈5 s), seek to 150 s lands at 153 s, seekable 0–183.4 s | same, clean |
| Firefox 155 | 1440 px; 390 px | picks the MP4, plays (5 s), seek to 150 s lands at 153–154 s | same, clean |

Standalone files in WebKit: the MP4 plays and seeks (120 s → 123 s); the WebM does not load in
this engine (it hung, and earlier crashed the page from `/demo`), which is why `/demo` now lists
the MP4 first. The WebM fallback was not exercised (all three engines here play H.264).

**Not tested:** Safari on a real iPhone or iPad, Safari on macOS, real Chrome/Edge/Firefox
releases on other operating systems. Playwright's WebKit on Windows uses a different media stack
from Apple's Safari, and mobile emulation is a viewport and user agent, not a phone. Nothing here
establishes Safari or iPhone compatibility; it shows that the server now gives WebKit the 206
responses it requires.

## Earlier on 2026-10-15

The first deployment (08868cf) had no Function: Pages answered range requests with 200 and the
whole file (smoke test 18 of 20). Cloudflare documents this
(<https://developers.cloudflare.com/pages/configuration/serving-pages/>); `_headers` cannot change
it. Cloudflare also blocks Python's default `Python-urllib` User-Agent (403); the smoke test sends
`furnace-smoke/1.0`.
