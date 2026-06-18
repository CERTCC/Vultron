---
source: ISSUE-1050
timestamp: '2026-06-18T22:29:03.308215+00:00'
title: Migrate embargo.py received use cases to single-BT shape (ADR-0022)
type: implementation
---

## Issue #1050 — Single-BT execution for embargo.py received use cases (Remove/Invite/Accept)

Migrated `InviteToEmbargoOnCaseReceivedUseCase` and
`AcceptInviteToEmbargoOnCaseReceivedUseCase` in
`vultron/core/use_cases/received/embargo.py` to the single-BT execution
shape required by ADR-0022 / CLP-10-005. Each `execute()` now builds one
tree via a `behaviors/` factory function, calls `execute_with_setup()`
exactly once under `actor_id=receiving_actor_id`, and handles the result.

To support the pattern, two BT node classes gained optional identity
override constructor args: `OptionalLookupParticipantNode` gains
`target_actor_id` and `RecordParticipantAcceptanceNode` gains
`accepting_actor_id`. These allow PEC lookups and acceptance recording to
target the correct subject actor even when the tree executes under the
receiving actor's identity.

`embargo.py` removed from `KNOWN_VIOLATIONS` in the architecture ratchet
test (`test_single_bt_execution_received_side.py`). Six existing tests
updated to pass `receiving_actor_id` per the single-BT requirement.
Side-effect fix: `AcceptInviteToEmbargoOnCaseReceivedUseCase` now correctly
passes `sync_port` to the single BT execution.

All 3486 unit tests pass. Black, flake8, mypy, pyright clean.

PR: [#1063](https://github.com/CERTCC/Vultron/pull/1063)
