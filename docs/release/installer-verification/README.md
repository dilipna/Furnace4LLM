# Windows installer evidence

This directory records executed observations, not a blanket release certification.
The exact source/runtime and environment are inside each record. No GPU run is added.

## First installed build: `3d8a93d`

- `installed-smoke-3d8a93d.json`: real installed-code browser journey with developer
  tools removed from child PATH, read-only Docker preflight, guided example, export,
  clean stop and lease reacquisition. Existing Windows user, not a fresh consumer profile.
- `qwen-cpu-first-failed.json`: initial preparation failed. The old harness continued
  and cascaded into StopIteration. The original preparation reason was not captured;
  do not invent one. The failed record is retained unchanged.
- `qwen-cpu-3d8a93d.json`: installed-runtime Qwen CPU journey passed 33 operational
  checks, with **11/12 model rules passed** and **12/12 outputs identical across
  relaunches**. The failed answer remains. This later run followed a successful explicit
  pinned-image pull and diagnostic instrumentation; that does not establish the exact
  cause of the first failure. The model, thresholds and expectations were not changed.

The public/product PNGs are actual installed-app captures from this build. They show
metadata and setup, not model inference. Newer CI installer builds have separate
receipts; they must not inherit this trial as if it ran on their exact bytes.

## Performance

`lighthouse-initial.json` is the unfavorable exploratory mobile audit: **42 performance,
100 accessibility, 100 SEO**, benchmark index 174. It measured a working-tree static
preview during concurrent build/model work, not a clean-head release test. Do not claim
a controlled speedup against it. Its main-thread/resource findings motivated removing
unneeded font preloads/prefetch and serving compressed text. The >=90 acceptance rule
is unchanged. Fresh final-head CI reports are separate artifacts, not replacements.

## Remaining human gates

Clean consumer-account/SmartScreen behavior, interactive uninstall data choices,
comprehension and an independent pilot require actual people. Browser automation and
fresh hosted runners are not evidence of those outcomes. Legal drafts and public
distribution licensing need owner review before publishing.
