# Participant test — observations not yet collected

Use separate sessions with one nontechnical participant and one developer unfamiliar
with Furnace. Allow about 15 minutes each. Ask them to think aloud; do not supply the
answers below. Record exact words, actions, hesitation, assistance and skipped tasks.
Report task completion separately from understanding. Browser automation is not human
feedback. No pass rate, participant result or investor approval exists yet.

## Nontechnical participant: comprehension without installation

The facilitator starts Studio on a review machine. Do not ask this participant to install
Python, uv or Docker. Let them explore the example and explanation independently. If
execution is unavailable, offer the dated review screenshot with its saved-result context.
If the facilitator operates the fixture or explains the screen, label that portion
**assisted observation**, not independent task completion. Do not imply a screenshot is
new execution. Prepare this context without coaching the answers.

| Prompt | Actual observations / assistance |
| --- | --- |
| Explain who Furnace is for and what the preview supplies today. | |
| Open the guided example. What has happened before any worker starts? | |
| Inspect results. Were these saved or newly executed? Did an LLM run? | |
| Explain an exact pass and an unscored case. What do they establish about answer quality or speed? | |
| Find the next step for someone's own model and explain what is still unavailable. | |

Facilitator rubric, withheld until afterward: metadata opening does not execute; a live
fixture uses deterministic uppercase output in Docker, not learned inference; saved
results retain their time/identity and reopening does not rerun them; exact equality is
not semantic quality, descriptions stay unscored, and duration includes Docker overhead.
Studio has no real-model adapter or active paid infrastructure service.

## Unfamiliar developer: prerequisites and execution

Provide the checkout/revision and application guide, a sanitized sample, and an empty
workspace. Prerequisites are Git, Python 3.12, uv and registry access for an uncached
install. Local Linux-container Docker is needed only for fixture execution. Do not
install it for the participant without agreement; if absent, mark execution **not run**
and still assess whether they correctly identify the requirement. First preparation may
download public images/packages. No GPU, model weights, Postgres or GitHub App is needed.

From the repository root: `uv sync --frozen`, then `uv run furnace studio`. Keep the
terminal open and use the private session link; never include that link in feedback.
Ctrl+C stops Studio and its owned workers.

| Prompt | Actual observations / assistance |
| --- | --- |
| Determine which prerequisites apply to inspection/export versus execution; explain whether this machine is ready. | |
| Start Studio, open the example and identify what has and has not executed. | |
| When Docker is available, prepare/start the fixture with consent, run its cases, and explain one exact pass plus one unscored result. | |
| Export the kit; locate project/configuration/execution provenance. Stop the worker, reload and explain the saved result. | |
| Find the real-model limitation and distinguish the existing endpoint CLI from Studio functionality. | |

The smallest remaining clean-install coverage is a fresh native Windows or macOS user
environment with Python 3.12 + uv, registry access and empty uv cache, using the exact
hashed preview ZIP outside the checkout. Expected: launch, metadata example, export and
restart persistence without Docker. Fixture execution is a separate test requiring local
Linux Docker. Debian 12 clean installation was tested previously; native coverage and
these participant observations remain uncollected. Documentation commands alone are not
verification.
