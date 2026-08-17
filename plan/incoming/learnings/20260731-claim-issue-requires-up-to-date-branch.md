---
title: claim-issue.sh exits non-zero when branch is behind origin/main
type: learning
timestamp: 2026-07-31
source: ISSUE-1873
signal: tooling-issue
---

`claim-issue.sh` failed with a non-zero exit code because the working branch was 16 commits behind `origin/main`.  The script apparently validates that the branch is current before labelling the issue.

Fix: always run `git fetch origin main && git rebase origin/main` (or equivalent) before invoking `claim-issue.sh` if the branch has been idle for any length of time.

**Promoted**: 2026-08-17 — captured in AGENTS.md pitfall: claim-issue.sh requires up-to-date branch.
Docs PR: TBD.
