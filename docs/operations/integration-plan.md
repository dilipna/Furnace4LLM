# Proposed integration order — no merge or publication authorization

Main remains `d893453`. This plan does not claim that the owner's November 24 walkthrough
or clean-account install/keep/delete has happened. Their observations are still missing.
The original walkthrough sheet and port 4010 candidate are unchanged.

1. **#18 Windows app:** review its final head/checks and the owner's actual walkthrough
   and clean-account results; then request merge approval. The lease-test race is fixed,
   self-hosted fonts replace Google build-time fetching, and the failed preload report
   remains recorded. Parallel Windows-suite fixture failures remain disclosed.
2. **Verify the resulting main:** use a normal merge commit to preserve ancestry and
   require fresh checks on main. A child's earlier green checks do not prove merged main.
3. **#19 document app:** merge that main into the branch without rewriting shared
   history, retarget to main and inspect the child-only diff. Recheck all five workflows
   on the resulting head. Owner gates: select the default/faster recipe after reading
   the comparison, accept or reject the remaining quality/staging limitations, and review
   installed acceptance and larger-document results. Do not represent 8/8 fixed attacks
   as solved prompt injection. Request merge approval; do not merge automatically.
4. **#20 public site:** after #19, retarget/update against main, preserve only the site
   changes and obtain fresh checks. Check that download metadata identifies the actual
   installer and recordings label their own source. Review security/FAQ claims and the
   complete negative results. Keep recorded-only hosting; a merge does not authorize deploy.
5. **#15 readable evidence:** update from current main, inspect the remaining summary
   changes and rerun checks. `git merge-tree` found no textual conflict against the
   inspected document/site stack; this is not a functional merge verification. It must
   inherit the local-font fix through main before claiming offline builds. Keep draft
   until the owner reviews the Advanced result summary on the integrated app.
6. **#16 portfolio docs:** update from current main. The inspected merge has a
   `.gitattributes` conflict: retain both evidence-byte and font-byte rules. Layout and
   README merged textually, but the README still needs editorial review against the new
   private-document front door. Preserve Earlier work and distinguish older Studio
   screenshots/records. Keep actual pilot observations blank and rerun checks.

Prefer merging current main into #15/#16 over rebasing shared branches. A rebase would
rewrite published history and need an explicit decision; no force-push is authorized here.
The actual integrated trees and checks must be verified after each main change, even
where this read-only merge simulation found no conflict.

Before a release: build fresh artifacts from the selected integrated source, verify
their hashes/installed behavior, complete licensing/legal review and obtain explicit
owner publication/deployment approval. Local QA candidates are not release artifacts.
