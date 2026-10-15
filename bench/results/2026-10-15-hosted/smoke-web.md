# Smoke test, 2026-10-15 02:35 UTC

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
| recording /demo/furnace-demo.webm streams | **fail** | 200 video/webm None |
| recording /demo/furnace-demo.mp4 streams | **fail** | 200 video/mp4 None |
| video poster | pass | 200 |
| recorded lab telemetry | pass | 200 |
| no API: POST /api/guard/runs | pass | 405 |
| no API: POST /api/public/scans | pass | 405 |
| no API: POST /api/live/bench | pass | 405 |
| no API: GET /api/live/status | pass | 404 |
| no API: GET /healthz | pass | 404 |
| unknown page is a 404 | pass | 404 |

Overall: FAIL
