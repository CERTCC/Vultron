---
title: "Pre-build dedup sets before fallback loops to avoid O(n²)"
type: learning
timestamp: 2026-07-14
source: ISSUE-1378
---

In `_resolve_case_manager_id`, the fallback loop used
`participant_ref in case.actor_participant_index.values()` to skip already-checked
IDs. Since `dict.values()` is a linear view, this made the fallback O(n×m) where
n = index size and m = case_participants length. Fix: build
`indexed_participant_ids = set(case.actor_participant_index.values())` once before
the loop, reducing each membership check to O(1).

**Pattern to apply:** whenever skipping items based on membership in a dict's
values inside a loop, pre-build a `set()` of those values before the loop starts.
