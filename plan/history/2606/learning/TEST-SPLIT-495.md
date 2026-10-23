---
source: TEST-SPLIT-495
timestamp: '2026-06-22T19:31:51.296707+00:00'
title: Stage new files and deleted files together when splitting
type: learning
---

When splitting a monolithic test file into several new files via `git rm` +
manual `create`, the new files are untracked until explicitly staged. A
pre-PR code review caught that the branch's committed diff only contained
the deletion (from `git rm`) while the four new files sat as untracked
working-tree files. Always run `git add <new-files>` alongside `git rm
<old-file>` before committing a file-split refactor.

**Promoted**: 2026-06-22 — archive only (routine git workflow practice).
Docs PR: <https://github.com/CERTCC/Vultron/pull/1112>.
