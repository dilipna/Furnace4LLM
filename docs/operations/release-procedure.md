# Release procedure (Studio download)

For the self-contained Windows installer and exact artifact/site verification, use
[Windows download operations](windows-download.md). The wheel-preview procedure below
still applies to that separate developer-oriented ZIP. Publication remains owner-approved.

How a Studio download goes from a reviewed commit to something people may install. Steps 1–5
are local and repeatable; step 6 is outward-facing and happens only with the owner's approval.

## 1. Start from a merged, reviewed commit on `main`

All changes arrive by pull request with hosted CI green (`python`, `web`, `image`,
`saved-measurements`). Run `bash scripts/ci_linux.sh` on the exact commit as well
(the pre-push hook expects it).

## 2. Re-run the real-model validation on that commit

```sh
uv run python scripts/validate_managed_model.py --model qwen2.5-0.5b-instruct-q8_0 --accelerator cpu --out docs/release/validation/COMMIT/real-model-qwen-cpu.json
uv run python scripts/validate_managed_model.py --model granite-4.0-h-350m-q8_0 --accelerator cpu --out docs/release/validation/COMMIT/real-model-granite-cpu.json
# and --accelerator nvidia on a machine with an NVIDIA GPU
uv run python scripts/render_model_validation.py --records-only docs/release/validation/COMMIT
```

Run from a clean tree (the record states the commit and whether the tree was clean).
Replace COMMIT with the source SHA and use a new directory for each attempt; keep failed
records and the historical table. Run only the models/accelerators selected for this release.
An operational pass and the model's rule score are separate results.

Any failed operational check blocks the release; record it, fix it, rerun. Do not edit thresholds or suite
expectations to make a run pass: a changed suite is a new suite version with a new digest.

## 3. Check the installed bundle outside the checkout

`scripts/verify_studio_onboarding.py` (clean caches, Docker absent and present) and
`scripts/verify_simple_interface.py` (public site and Studio in headless browsers).

## 4. Build the release candidate

```sh
uv run python scripts/package_release.py
```

Writes `dist/release/furnace-studio-<version>+<commit>.zip`, `SHA256SUMS` and
`release.json` (version, commit, file and wheel hashes, verified platforms read from the
recorded runs). It refuses a dirty tree and checks that the packaged reference suite matches
its pinned digest.
With `--skip-build`, the existing bundle must match this commit, dirty state, version and
wheel bytes. Stale or altered inputs are refused before existing release output is replaced.
Untracked source files also make the checkout dirty. `--allow-dirty` is for labelled local
experiments, not a way to relabel a bundle from another commit.
Platform records include their original evidence commits and are historical observations,
not proof that this newly built ZIP has passed those tests. Install and validate it separately.

## 5. Review the candidate

- `release.json` → `verified_platforms` matches what the release notes claim; nothing listed
  under `not_verified` is described as supported.
- Install the ZIP once on a fresh user profile of each OS the notes name.
- Release notes state limits (small models, one suite, rule checks are not quality
  judgements, no hosted service) as plainly as features.

## 6. Publish (owner approval required)

Create a GitHub release for the tag, attach the ZIP, `SHA256SUMS` and `release.json`, and
link it from the website download page. SHA-256 sums detect corruption, not a forged
publisher: signing (for example Sigstore or platform code signing) is still to be chosen.
Website deployment follows `docs/deploy.md` and also needs owner approval.

## Rolling back

Mark the GitHub release as a pre-release or delete its assets, point the download link to
the previous release, and record why in the release notes. Local workspaces are unaffected:
a newer Studio does not migrate data destructively, and older evidence stays labelled with
the protocol and scorer versions that produced it.
