---
title: "freshen-branch.sh misreports 'already rooted' when origin/main ref is ambiguous"
type: learning
timestamp: "2026-08-25T00:00:00Z"
source: ISSUE-2572
signal: tooling-issue
---

`freshen-branch.sh` uses `origin/main` as the upstream ref. When a local branch named
`origin/main` exists alongside the remote-tracking ref `refs/remotes/origin/main`, git
reports `warning: refname 'origin/main' is ambiguous` and resolves to the local branch.

This caused the script to report "Branch already rooted at origin/main — nothing to do"
even though the task branch was one merge-commit behind the true `refs/remotes/origin/main`
tip. The workaround was a manual `git rebase refs/remotes/origin/main`.

The fix should update `freshen-branch.sh` (and any other skill script that references
`origin/main`) to use the unambiguous form `refs/remotes/origin/main` throughout.

**How to reproduce**: have a local branch named `origin/main` in the repo and run
`freshen-branch.sh` while the task branch is behind remote main.

**Promoted**: 2026-08-27 — archived (already in specs/notes/AGENTS.md or tracked as GitHub issue). Docs PR: <pending>.
