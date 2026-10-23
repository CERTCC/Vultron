---
title: "SKIP=black needed when rebasing in any vultron_* worktree"
type: learning
timestamp: 2026-07-08T00:00:00+00:00
source: ISSUE-1061
---

When rebasing in any `vultron_*` git worktree, the pre-commit hook runs
`black` in-place during cherry-pick. Black reformats files after git applies
the patch but before the cherry-pick completes, leaving a dirty working tree
that blocks the merge step with "Your local changes to the following files
would be overwritten."

**Fix**: `SKIP=black git rebase origin/main`

This skips only the black hook for that rebase; black is already enforced at
commit time and CI, so nothing is bypassed.

**Why it happens**: The `.git/hooks/pre-commit` points to a Python
interpreter in a sibling worktree's `.venv`, which runs `pre-commit` against
the current working tree. During rebase cherry-pick, git applies changes then
runs hooks — if black reformats any of those files, git sees them as newly
modified and refuses to continue.

**Scope**: Only affected rebases that touched Python files that black would
reformat (import ordering, line length, etc.).

**Resolved**: Fixed in #1260 by adding `--check` to the `black` hook and
removing `--fix` from the `markdownlint-cli2` hook in `.pre-commit-config.yaml`.
Hooks are now fail-only; auto-fix is done by the `format-code`/`run-linters`
skills before committing. The `SKIP=black` workaround is no longer needed.

**Promoted**: 2026-07-08 — resolved/superseded; already captured in
`AGENTS.md` § "Pre-commit Hooks Are Fail-Only". No new doc changes needed.
Docs PR: [#1274](https://github.com/CERTCC/Vultron/pull/1274)
