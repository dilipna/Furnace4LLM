# Smoke test, 2026-10-15 21:56 UTC

web `https://furnace-5h6.pages.dev` (recorded-only, no API)

| check | result | detail |
|---|---|---|
| page / | pass | 200 |
| page /demo | pass | 200 |
| page /pilot | pass | 200 |
| page /bench | pass | 200 |
| page /guard | pass | 200 |
| page /guard/r1_dynamic_head | pass | 200 |
| page /lab | pass | 200 |
| page /evals | pass | 200 |
| /pricing redirects to /pilot | pass | https://furnace-5h6.pages.dev/pilot#terms-h |
| pilot contact link | pass | https://www.linkedin.com/in/dilip-n-ab1091417/ |
| furnace-demo.webm: full GET | pass | 200 len 13581918/13581918 type video/webm accept-ranges bytes |
| furnace-demo.webm: bytes=0-1 -> 206 | pass | 206 bytes 0-1/13581918 len 2 (want 2) |
| furnace-demo.webm: bytes=100-199 -> 206 | pass | 206 bytes 100-199/13581918 len 100 (want 100) |
| furnace-demo.webm: bytes=1000000-1000999 -> 206 | pass | 206 bytes 1000000-1000999/13581918 len 1000 (want 1000) |
| furnace-demo.webm: bytes=13581908- -> 206 | pass | 206 bytes 13581908-13581917/13581918 len 10 (want 10) |
| furnace-demo.webm: bytes=-100 -> 206 | pass | 206 bytes 13581818-13581917/13581918 len 100 (want 100) |
| furnace-demo.webm: bytes=0-27163836 -> 206 | pass | 206 bytes 0-13581917/13581918 len 13581918 (want 13581918) |
| furnace-demo.webm: bytes=13581918- -> 416 | pass | 416 bytes */13581918 |
| furnace-demo.webm: multiple ranges -> 200 whole file | pass | 200 len 13581918 |
| furnace-demo.webm: malformed range -> 200 whole file | pass | 200 len 13581918 |
| furnace-demo.webm: stale If-Range -> 200 whole file | pass | 200 len 13581918 |
| furnace-demo.webm: HEAD with Range | pass | 206 bytes 0-1/13581918 body 0 |
| furnace-demo.mp4: full GET | pass | 200 len 3442223/3442223 type video/mp4 accept-ranges bytes |
| furnace-demo.mp4: bytes=0-1 -> 206 | pass | 206 bytes 0-1/3442223 len 2 (want 2) |
| furnace-demo.mp4: bytes=100-199 -> 206 | pass | 206 bytes 100-199/3442223 len 100 (want 100) |
| furnace-demo.mp4: bytes=1000000-1000999 -> 206 | pass | 206 bytes 1000000-1000999/3442223 len 1000 (want 1000) |
| furnace-demo.mp4: bytes=3442213- -> 206 | pass | 206 bytes 3442213-3442222/3442223 len 10 (want 10) |
| furnace-demo.mp4: bytes=-100 -> 206 | pass | 206 bytes 3442123-3442222/3442223 len 100 (want 100) |
| furnace-demo.mp4: bytes=0-6884446 -> 206 | pass | 206 bytes 0-3442222/3442223 len 3442223 (want 3442223) |
| furnace-demo.mp4: bytes=3442223- -> 416 | pass | 416 bytes */3442223 |
| furnace-demo.mp4: multiple ranges -> 200 whole file | pass | 200 len 3442223 |
| furnace-demo.mp4: malformed range -> 200 whole file | pass | 200 len 3442223 |
| furnace-demo.mp4: stale If-Range -> 200 whole file | pass | 200 len 3442223 |
| furnace-demo.mp4: HEAD with Range | pass | 206 bytes 0-1/3442223 body 0 |
| /demo is static (no Function) | pass | 200 x-furnace-range=None |
| /demo/poster.png is static (no Function) | pass | 200 x-furnace-range=None |
| / is static (no Function) | pass | 200 x-furnace-range=None |
| /demo/__next._full.txt is static (no Function) | pass | 200 x-furnace-range=None |
| video poster | pass | 200 |
| recorded lab telemetry | pass | 200 |
| no API: POST /api/guard/runs | pass | 405 |
| no API: POST /api/public/scans | pass | 405 |
| no API: POST /api/live/bench | pass | 405 |
| no API: GET /api/live/status | pass | 404 |
| no API: GET /healthz | pass | 404 |
| unknown page is a 404 | pass | 404 |

Overall: pass
