# Self-hosted font verification

Fonts and OFL licenses are vendored from the pinned google/fonts revision in
`apps/web/app/fonts/sources.json`. No build-time font-service fetch is needed.

The first self-hosted-font Windows workflow failed the unchanged Lighthouse >=90
rule: performance 75, accessibility 100, SEO 100. Raw report is retained losslessly
in lighthouse-preload-failure.json.gz; workflow 45550306213. The report shows four
high-priority preloaded TTF downloads totalling 985,596 font bytes, although the
installer landing page uses Arial. LCP was 7.8 seconds. This is concrete unnecessary
network work, not proof that every score difference has one cause.

The correction disables eager preload of the four font files. They remain bundled
and available to pages that use their CSS variables. The landing page need not fetch
fonts it does not use. Thresholds are unchanged; new exact-head CI must pass.

A local #16 production build passed with Node outbound sockets denied and telemetry
disabled, after a cached offline dependency install. This verifies that build operation,
not installation of all developer prerequisites on an air-gapped machine. The unchanged
November 24 walkthrough static output and installer remain separate.
