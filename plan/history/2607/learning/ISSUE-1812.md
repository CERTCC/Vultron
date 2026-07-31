---
title: "_resolve_case_manager_id inlined in develop_fix.py to avoid BTND-04-003"
type: learning
timestamp: "2026-07-29T00:00:00Z"
source: ISSUE-1812
signal: design-question
---

During implementation of `create_develop_fix_tree` (ISSUE-1812), the helper
`_resolve_case_manager_id` was needed by `EmitCFActivity` to find the case
manager participant. The canonical source lives in
`vultron.core.use_cases._helpers`, but behaviors layer cannot import use_cases
(BTND-04-003).

Decision: inline the function directly in
`vultron/core/behaviors/report/nodes/develop_fix.py` with a docstring noting
it mirrors the canonical source. The inlined version faithfully reproduces
both the fast-path (`actor_participant_index`) and the fallback iteration over
`case_participants`.

Long-term unification (deduplicate to a shared `core.behaviors` helper or
move the canonical to a layer both can import) is tracked by #1428.

**Promoted**: 2026-07-31 — captured in `notes/bt-pitfalls.md` (_resolve_case_manager_id duplication section).
Docs PR: TBD.
