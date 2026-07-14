---
title: "Consolidating dual-path helpers: primary path requires its own test"
type: learning
timestamp: 2026-07-14
source: ISSUE-1378
---

When consolidating two helpers that each cover a different lookup path into one
unified function, the new test suite must explicitly exercise each path in
isolation. In ISSUE-1378, the unified `_resolve_case_manager_id` had a primary
`actor_participant_index` path and a fallback `case_participants` path. All 6
initial tests only populated `case_participants`, leaving the primary path
entirely untested. The gap was caught by code review and a 7th test
(`test_primary_index_path_returns_actor_id`) was added before the PR.

**Pattern to apply:** when a consolidated helper has N distinct lookup paths,
ensure at least one test per path where that path is the sole source of truth
(i.e. the other paths are left empty or unpopulated).
