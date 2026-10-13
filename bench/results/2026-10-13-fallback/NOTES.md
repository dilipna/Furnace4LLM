# Does uncertain or unsupported analysis widen the checks, or silently skip them? (2026-10-13)

Question (owner, 2026-10-13): when Guard's impact analysis cannot account for a change, does
it fall back to broader checks, or does it skip checks that matter? And does Scan say what it
could not read?

## Guard: verified by tests written before the fix

The documented rule was "an application-code change that maps to no fact selects the full
suite". It held only for *modified Python lines*. Seven tests were written against the code
at d2df18d (`packages/furnace/tests/test_impact.py`, section "uncertain or unsupported
analysis"); **six failed** (no fallback, and in five of them no category either, so nothing
but the always-on checks ran):

| change in the PR (on F1) | before (d2df18d) | after |
|---|---|---|
| an article in `docs/` that `app/retriever.py` loads (`(ROOT / "docs").glob("*.md")`) | category `docs`, nothing selected | full suite: "read by application code (app/retriever.py:28)" |
| a TypeScript file added under `app/` | skipped, no category | full suite: "source the analysis does not parse" |
| an unmodelled data file in the app (`app/data/thresholds.csv`) | skipped, no category | full suite: "a file the analysis does not model" |
| an added Python module that maps to no graph node | skipped (added files have no hunks) | full suite |
| a removed Python module that maps to no graph node | skipped | full suite |
| an app module that no longer parses | treated as removed nodes | full suite: "does not parse as Python" |
| CI workflow, an image, CHANGELOG (inert) | no fallback | no fallback (unchanged, the seventh test) |

A template the scanner models (`.j2`) is still targeted, not a fallback (its prompt node is
touched). Rule now (`guardian/impact.py`): a changed file is either mapped to graph nodes,
or known to be inert (tests, CI, repository metadata, images, docs nothing reads), or it
selects the full suite with the reason. "Read by application code" is a string-literal
heuristic on the file name or its directory; it errs toward a fallback, which only widens.

## Effect on results already reported

- RQ3 (13 F1 PR scenarios, `2026-10-06/rq3/`): selection recomputed under the new rule is
  identical in 13/13 scenarios (`docs_only` edits the README, which nothing reads). RQ3 never
  exercised the cases above, so its "targeted ran 46% of checks" is unchanged and says nothing
  about them.
- Held-out set 4 synthetic PRs (`external_validation.md` here vs `2026-10-12-reconcile/`): the
  Guard table is identical, 9/9 correct.

## Scan: what it could not read

Unchanged and verified: a repository whose source is in a language other than Python gets a
coverage box on the Blueprint naming the languages and their share, and an empty Blueprint
says "a coverage limit, not a clean bill of health". New: Python files the extractor skips
(syntax errors, Python 2, files over 2 MB) were silently dropped; they are now listed in the
scan's stats (`python_not_analyzed`) and in the same coverage box.
