---
source: ISSUE-896
timestamp: '2026-06-11T18:12:59.093135+00:00'
title: 'Fix Invite/Accept routing: Case Actor as sender/recipient; remove identity
  spoofing'
type: implementation
---

## Issue #896 — Fix Invite/Accept routing: Case Actor as sender/recipient; remove identity spoofing

Fixed two PCR-08 spec violations in the Invite/Accept handshake.

**PCR-08-007**: `SvcInviteActorToCaseUseCase` now resolves the Case Actor ID
and builds the Invite with `actor=case_actor_id` (falling back to owner when
no Case Actor Service exists yet), placing it in the **Case Actor's outbox**.

**PCR-08-009/010**: `AcceptInviteActorToCaseReceivedUseCase` no longer
identity-spoofs. The `PrioritizeBT(actor_id=invitee_id)` call executed from
the Case Actor's DataLayer context was removed. `RM.ACCEPTED` is now
pre-seeded inline before participant creation, eliminating the spurious
`RmEngageCaseActivity` (Join) emission from a foreign DataLayer context.

**Supporting changes**:

- `_find_case_actor_id` moved to `vultron/core/use_cases/_helpers.py` (shared)
- `TriggerActivityPort.invite_actor_to_case` gains `attributed_to` param
- `TriggerActivityAdapter` passes `attributed_to` when set
- Demo `invite_actor_demo.py` routes Accept to Case Actor inbox

**Integration test fix**: `test_pcr_late_joiner.py` fixture now patches
`VULTRON_SERVER__BASE_URL` to `{_OWNER_BASE}/api/v2` (same pattern as
`test_pcr_engage_case.py`) so Case Actor IDs are routable. Explicit
`_drain_case_actor_outbox` call added after invite trigger since the Invite
is now in the Case Actor's outbox, not the owner's.

PR: <https://github.com/CERTCC/Vultron/pull/899>
