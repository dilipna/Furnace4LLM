# Windows installer evidence

This directory records executed observations, not a blanket release certification.
The exact source/runtime and environment are inside each record. No GPU run is added.

The [provisional Studio preview 9598d6d](candidate-9598d6d/README.md) has installed
Qwen/Granite CPU, browser/kit, install and uninstall records. A separate
[November 28 CPU document acceptance](candidate-9598d6d/document-2026-11-28/README.md)
now covers its installed document suite and browser workflow. It is not the December 4
final installer. The final
rebuilt binary must pass both journeys on its exact bytes. Earlier records below
are historical and cannot substitute for that acceptance.

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

## Subsequent executed checks

- Windows CI at `a836fc8`: [run 45269076892](https://github.com/dilipna/Furnace4LLM/actions/runs/45269076892)
  passed native install/window lifecycle, browser preflight/example/export, lease
  release, uninstall/data retention, actual download/hash and site checks.
  Lighthouse 13.0.1 measured **97 performance / 100 accessibility / 100 SEO**.
  The run artifacts contain the raw report and installer-specific receipts.
- `lighthouse-local-reviewed.json`: local working-tree preview, Lighthouse 13.0.1,
  **100 / 100 / 100** after recording/build work finished. This is separate from
  exact-head hosted results and is not a controlled comparison with the initial run.
- `recording-3d8a93d.json`: actual installed Qwen CPU browser recording receipt.
  Cached preparation assets; automated interaction, not a human comprehension test.
  Rule score **11/12**, cross-launch identical outputs **12/12**, deliberate crash,
  explicit refresh/consent/restart, and clean shutdown/lease release. Media stays
  local and unpublished in generated preview output. Installation is shown with
  separate real stills, not continuous installation footage.
