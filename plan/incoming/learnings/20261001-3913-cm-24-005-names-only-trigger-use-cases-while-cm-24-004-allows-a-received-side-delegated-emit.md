---
title: "CM-24-005 requires the shared delegated-authorship helper of trigger use cases only, while CM-24-004 routes a delegated emit through the CASE_MANAGER's received tree — the received side has no helper and cannot import the one that exists"
type: learning
timestamp: "2026-10-01T00:35:00Z"
source: ISSUE-3913
signal: spec-gap
---

CM-24-004 (as amended by ADR-0109) says a participant whose container does not
host the CASE_MANAGER sends the manager its own activity and "the CASE_MANAGER's
received tree performs the delegated emit". CM-24-005 then says "All trigger use
cases that emit delegated Activities MUST use a shared helper (e.g.
`_prepare_delegated_context()`)" and "No callsite may independently reconstruct
the delegated-authorship pattern without going through this shared helper."
Issue #3913 AC-2 read the second sentence as binding the received-side relay
too.

It cannot be satisfied there as written. `_prepare_delegated_context()` lives in
`vultron/core/use_cases/triggers/_helpers.py`; a BT node under
`vultron/core/behaviors/` may not import from `use_cases/` (BTND-04-003, ratchet
`test_behaviors_no_use_case_imports.py`). Its fallback arm ("no CaseActor → send
as the requester, `attributed_to=None`") is the one CM-24-006 retires (#3964).
And it answers a question the received tree never asks: the relay runs only
under `create_case_manager_gated_tree`, so `actor` *is* the role holder by
construction, and `attributed_to` is the proposer the manager just adjudicated.
`RelayEmbargoInviteToEachNode` therefore holds CM-24-001/002 structurally and
records the deviation in its docstring and `notes/case-communication-model.md`.

The gap: CM-24 has a helper requirement for the trigger side and none for the
received side it also sanctions. A second received-side delegated emit (the
creation-time revision of EP-04-011, #3916, is the obvious next one) will face
the same choice. Either CM-24-005 should say the role gate *is* the received
side's shared mechanism, or a received-side helper should be named.
