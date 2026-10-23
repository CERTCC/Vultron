---
source: TASK-PRM
timestamp: '2026-05-04T19:26:02.425252+00:00'
title: Participant Role Management
type: implementation
---

## TASK-PRM — Participant Role Management

Added `roles` read-only property to `VultronParticipant` returning a copy of
`case_roles` (PRM-01-001); added the same property plus aligned `add_role()`,
`remove_role()`, and `has_role()` to `CaseParticipant` (PRM-04-001); updated
subclass `model_validator` methods to use `add_role()` (PRM-04-002 SHOULD);
added `roles` property stub to `ParticipantModel` Protocol so mypy resolves
callers correctly; migrated `action_rules.py` line 139 from `participant.case_roles`
to `participant.roles` (PRM-01-003, PRM-03-001); created
`test/core/models/test_participant.py` with 20 unit tests covering
`add_role()`, `remove_role()`, `has_role()`, and `roles` (PRM-05-001 through
PRM-05-003); added `test/architecture/test_participant_case_roles.py`
enforcing no direct `case_roles` mutation in `vultron/core/` outside
`participant.py` (PRM-05-004). All 2284 tests pass; pyright clean; only
pre-existing mypy error in `inbox_handler.py` (unrelated).
