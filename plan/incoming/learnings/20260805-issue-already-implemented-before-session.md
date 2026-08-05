---
title: Issue already fully implemented before session began (ISSUE-1858)
type: learning
timestamp: 2026-08-05
source: ISSUE-1858
signal: process-issue
---

When the build session for ISSUE-1858 began, the core implementation
(SvcLeaveCaseUseCase, receive_close_case_tree role discriminator, announce-tree
CloseCaseEffects slot, demo_close_case rewire) was already fully present at
HEAD, landed via PRs #1901, #1965, and #1966 during the period the original PR
PR 1909 was set aside.

The issue remained OPEN with an OPEN PR (#1909) despite the implementation
being complete, because the gap was in *test coverage* (AC-5 round-trip,
announce-tree close-case tests, demo endpoint tests) — not in code. The issue
comment history on #1858 documented the upstream impacts but did not explicitly
note that the core work was done.

Going forward: when picking up a previously-set-aside issue, the first step
after orient+deepen should include an explicit diff of what the issue requires
vs. what is already at HEAD — not just what the stale PR branch contains.
The `claim-issue.sh` guard (branch already exists) is a signal that prior
work may have landed via other paths.
