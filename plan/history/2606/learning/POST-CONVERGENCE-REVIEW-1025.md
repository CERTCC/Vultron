---
source: POST-CONVERGENCE-REVIEW-1025
timestamp: '2026-06-22T19:36:36.838235+00:00'
title: 'Post-convergence review: validate state machine transitions after multi-PR
  merges'
type: learning
---

After merging multiple PRs that independently touched state machine transition
logic, run a dedicated post-convergence integration sweep: (1) run the full
test suite with `-m ""`, (2) walk each `RM_TRANSITIONS` and `EM_TRANSITIONS`
dict looking for unreachable states, (3) check that every `ValidateTransitionNode`
variant covers the new transitions, (4) run the demo end-to-end. This sweep
is not automated by the normal CI run. Add a comment in the relevant SKILL.md
or build notes after the review.

**Promoted**: 2026-06-22 — archive only.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1112>.
