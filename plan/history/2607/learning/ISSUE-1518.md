---
title: "git rebase 'local changes would be overwritten' false positive"
type: learning
timestamp: "2026-07-20T00:00:00+00:00"
source: ISSUE-1518
---

During the create-pr phase, `git rebase origin/main` persistently failed with
"Your local changes to the following files would be overwritten by merge" even
though `git status --porcelain` showed a clean working tree and `git diff HEAD`
was empty. All listed files were already committed in HEAD.

**Root cause (hypothesis):** The origin/main branch had received concurrent
commits (#1517) that touched the same files as the branch being rebased. Git's
apply-based rebase mode may pre-check whether the patch can be applied cleanly
and error on "would overwrite" when both sides touched the same file — even when
there are no uncommitted local changes. The error message is misleading.

**Fix:** Used `git cherry-pick` onto a fresh branch rooted at origin/main
instead of `git rebase`. One real content conflict emerged (a single
`_build_tree` call in report.py needing both `offer_id=self._offer.offer_id`
from our branch and `captured=self._captured` from #1517). Resolved manually,
then `cherry-pick --continue`.

**Pattern to apply:** When `git rebase` fails with the "local changes" error
and the working tree is provably clean, try cherry-picking onto a fresh branch
from origin/main as an alternative path. The rebase error is NOT evidence of
uncommitted work.

**Promoted**: 2026-07-22 — captured in `AGENTS.md (root)`.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1608>8>8>.
