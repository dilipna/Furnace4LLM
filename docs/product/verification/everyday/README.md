# Evidence identities

The original `everyday-qwen-1.5b-*-2c250d6.json` records keep their published Git bytes
and v2 verdicts. `rescore-v3-committed-inputs.json` is the final post-hoc derivation
from those exact committed records: its input hashes match their Git blobs. No new
inference occurred during re-scoring.

The two preliminary `rescore-v3*.json` files used the original Windows working-copy
bytes. Their hashes resolve to the same basenames under `windows-input-bytes/`.
These differ from the published originals only in JSON line endings, not observations
or scores. Both preliminary derivations are retained; neither replaces the originals.
The archived v1 suite preserves its recorded exact bytes and has a clean-checkout
regression check. A copied helper/input tree materialized directly from Git blobs
reproduced CPU 9 pass / 2 fail and GPU 8 pass / 3 fail under the revised rules.

The six `comparison-*.json` records are real source-checkout trials. Source commits,
dirty flags and workflow hashes are explicit; do not call them installed builds.
`comparison-v3-summary.json` derives every planned case, including execution failures,
against `everyday-suite-v2-trials.json`. The original failed mitigation and CPU timeout
are retained. Memory samples are not continuous peaks, and timings are uncontrolled
observations on a shared host. See `../../model-comparison.md`.

The PDF records use a separate synthetic fixture identified by `suite_override` and
the archived fixture hash. They are not extra cases silently added to the 36-case median.
Recordings and installed confirmations identify their actual installer source; later
documentation commits do not turn them into fresh measurements of a different binary.
