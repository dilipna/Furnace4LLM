# Pin local verification to one commit — 2026-11-16

The integration review found that `ci_linux.sh` read HEAD separately for Python
staging, Web staging, API-image staging and the final pre-push pass stamp. HEAD could
move during a long run, causing mixed-source verification and a stamp for a commit
that had not passed all jobs. The displayed short SHA did not prevent that race.

A regression executes the actual Bash script against a temporary real Git repository,
using a Docker transport stub that records real archive contents. After the first
archive, the stub checks out a different prepared commit. Before the fix, the test
failed: contexts were `initial, changed, changed`, and the stamp named the changed
commit. The test never changes this project's checkout or contacts a Docker daemon.
Its successful stubbed job messages are orchestration evidence, not application CI.

The script now captures one full `COMMIT` at startup, archives it in every job and
writes that same identity to the pass stamp. HEAD can move without granting the newer
commit a pass. Check selection, assertions, thresholds and runner images are unchanged.
The local preinstalled-Node workaround remains a separate, explicitly documented
runner-image substitution. Existing results retain their captured source identities;
this correction does not retrospectively certify another head.

Repeat the regression with:

```sh
uv run pytest packages/furnace/tests/test_ci_commit_identity.py -q
```

Bash and Git are required (Git Bash on Windows). Real full Linux jobs must still run
on the final review head; a stubbed Docker orchestration regression cannot replace them.
