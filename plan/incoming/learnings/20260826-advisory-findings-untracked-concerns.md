---
title: "Untracked pre-existing concerns found during #2481 code review"
type: learning
timestamp: "2026-08-26"
source: ISSUE-2481
signal: concern
---

The Phase 7 code review for PR #2683 surfaced four pre-existing findings in files
not modified by that PR. They were posted as [ADVISORY] on the PR but no GitHub
issues were created. Each warrants a Concern issue:

1. **`vultron/core/behaviors/status/nodes/cs_dimension_filter.py:211`** — In-place
   dict mutation without writing to output port. Changes to `filtered` are never
   stored back to the blackboard; the filter silently has no effect.

2. **`vultron/core/behaviors/status/nodes/case_status.py:291`** — Save ordering
   issue: `dl.save(case_status)` is called before `case_status.add_dimension(...)` in
   one branch, meaning the dimension may not be persisted.

3. **`vultron/core/behaviors/status/nodes/case_status.py:108`** —
   `ValidateCaseStatusTransitionNode` is no longer wired into any BT; CS transition
   validation is silently skipped at runtime.

4. **`vultron/core/behaviors/call_out/bundles/actor_discovery.py:57`** — Actor
   discovery protocol bundle cannot receive `actor_id` from the blackboard — no read
   node is wired before the discovery action.

Note: the fifth finding (`vultron/core/use_cases/triggers/actor.py:223`) is already
related to tracked issue #2469.

Action: create one Concern issue per untracked item above before the next build
session that touches `vultron/core/behaviors/status/` or `call_out/`.
