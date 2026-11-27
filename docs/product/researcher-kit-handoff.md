# Researcher starter-kit handoff

The free journey is project inspection → exported kit → reviewed evaluation cases →
the same project's model workspace. It does not provision a hosted service.

Research projects now lead to real model operations after preparation; they no
longer require the deterministic fixture to complete onboarding. The guided example
keeps its fixture journey. A fixture run cannot complete the researcher project's
Model evaluated step; that requires a current endpoint attempt covering its cases.
A failed rule still counts as an executed result, not as a successful quality check.

## Corrected behavior

The CLI kit previously wrote `id` with null `input` and `expected_behavior` fields.
Studio's case format requires `name` and nonempty strings, and rejects unknown fields.
An actual API regression reproduced HTTP **422** when saving that exported case.

The kit now contains a Studio-compatible illustrative arithmetic case with a numeric
rule. Its answer (180 minutes) is authored, not measured model evidence. Researchers
must replace/review this example for their own task. Importing resets status to
`not_run`, executes nothing and does not create an evaluation result.

Previously the model workspace selected the first saved project, even when opened
from a different project's workspace. Links now carry `?project=<id>` in both
directions; reload preserves that selection. An explicit unavailable project is
refused rather than silently replaced with another. The session token remains in
session storage after the launch fragment is removed, never in the project query.

## Try the journey

1. Inspect a local model folder in Studio. Export its starter ZIP, or use
   `furnace starter <absolute-project-folder> --output <new-folder-outside-project>`
   from an installed Furnace Python environment.
2. Review/edit `evaluation-cases.example.jsonl` using sanitized task examples.
3. Select the intended project → Checks → import the JSONL → review its preview →
   explicitly replace saved cases. They must say Not run.
4. Open **Model infrastructure**. Confirm the same project is selected, including
   after reload. Back to workspace must return to that project.
5. Choose a reviewed recipe, a reviewed Python adapter or a compatible existing
   local server. Preparing/starting/connecting still requires explicit consent.
   Model execution has its own Docker/runtime prerequisites; kit export/import does not.

## Executed verification

- `uv run --frozen pytest -q apps/api/tests/test_starter_handoff.py`
  reproduces the old rejection and verifies actual persistence after the fix.
- `node --test apps/api/tests/studio-state.test.mjs` includes requested, missing,
  empty and deleted project selection, plus query encoding.
- The `studio_journey` in `scripts/verify_simple_interface.py` exports a real CLI
  kit, uploads it through the browser parser, saves it through the API, downloads
  the UI ZIP and compares the re-exported case. It checks second-project navigation,
  reload and refusal of a missing project. The committed
  [browser record](verification/researcher-kit-handoff/browser.json) identifies the
  source files and actual checks.

The browser uses a disposable workspace and scripted local HTTP server. Docker
readiness is simulated unavailable and Docker execution is forbidden in this check.
This is not real-model inference, an installed-binary test, a human comprehension
test, or managed-service acceptance. Existing historical model records are unchanged.
