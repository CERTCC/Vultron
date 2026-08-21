---
title: Issue #1467 plan-issue sync was already fixed on origin/main
type: learning
timestamp: 2026-08-21
source: ISSUE-1467
signal: process-issue
---

Issue #1467 listed `plan-issue` as missing its sync step (sync-check.sh was
in Phase 4 instead of Phase 0). When we checked `origin/main` before starting,
`plan-issue` already had Phase 0b (sync before orient-agent). The only remaining
fix was `bugfix`, which still had no sync step.

The issue body was partially stale at the time it was worked. The user's
instruction to "make sure the problem still exists in origin/main" correctly
identified this risk. Habit: always verify all stated defects against
`origin/main` HEAD before implementing, not just after a `git fetch`.
