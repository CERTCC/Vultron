---
source: ISSUE-1033
timestamp: '2026-06-18T14:33:41.323798+00:00'
title: 'Fix RemoveEmbargoEventFromCaseReceivedUseCase: single-BT pattern (CLP-10-003)'
type: implementation
---

## Issue #1033 — Fix RemoveEmbargoEventFromCaseReceivedUseCase: replace foreign-actor commit with pre-flight guard (CLP-10-003)

Replaced the CLP-10-003-violating pattern (resolving CaseActor ID and passing
it as `actor_id` to a second `execute_with_setup` call) with the correct
single-BT approach:

- `remove_embargo_from_case_tree` restructured to embed the guarded commit as
  the final child of the outer Sequence. A new `TeardownIfActive`
  Selector(Sequence, Success) absorbs the FAILURE from `IsActiveEmbargoNode`
  when the embargo was only in `proposed_embargoes`, so the commit step is
  always reached.
- `RemoveEmbargoEventFromCaseReceivedUseCase.execute()` now makes a single
  `execute_with_setup` call with `actor_id=receiving_actor_id`. An explicit
  `None` guard handles missing `receiving_actor_id`. `CheckIsCaseManagerNode`
  inside the tree provides the role-based gate — no identity comparison in
  Python.
- `TestRemoveEmbargoRoutingGuard` (2 new tests) added to
  `test_embargo_routing_guard.py`.
- 4 existing `test_embargo.py` tests updated to pass `receiving_actor_id` in
  `make_payload` calls (previously omitted, which would now skip the BT).
- Filed #1038 to track the same fix for `InviteToEmbargoOnCaseReceivedUseCase`
  and `AcceptInviteToEmbargoOnCaseReceivedUseCase` (more complex because those
  trees need a different `actor_id` for main ops vs. the commit).

PR: [#1037](https://github.com/CERTCC/Vultron/pull/1037)
