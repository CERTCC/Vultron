---
source: CONCERN-1747
timestamp: '2026-08-05T14:55:12.824047+00:00'
title: 'concern: RejectInviteActorToCase ledger commit unreachable — Reject(Invite)
  carries case_id in inner_target not target'
type: learning
---

## Concern

`RejectInviteActorToCaseReceivedUseCase.execute()` reads `request.target_id`
(from `request.target`) to resolve the `case_id`. However,
`Reject(Invite(actor, case))` carries the case reference in the nested
Invite's `target` field (`inner_target`), not at the top-level `target` of
the Reject activity.

`extract_event` populates `inner_target` but not `target`, so
`request.target_id` is always `None`.

The use case early-returns with a warning log and **never reaches** the BT
that would commit the canonical `Reject(Invite)` ledger entry.

## Fix

In `RejectInviteActorToCaseReceivedUseCase.execute()`
(`vultron/core/use_cases/received/actor/invite.py`), change:

```python
case_id = request.target_id
```

to:

```python
case_id = request.inner_target_id or request.target_id
```

Also add a `case_id` convenience property to
`RejectInviteActorToCaseReceivedEvent` (parallel to
`AcceptInviteActorToCaseReceivedEvent.case_id`) returning `inner_target_id`.

## Evidence

Test `test_reject_invite_skips_ledger_when_target_id_absent` in
`test/core/use_cases/received/actor/test_invite.py` documents and confirms
the current (broken) behaviour.

## History

Pre-existing gap introduced in #1293. Discovered and documented during PR #1746
(Issue #1689). Not introduced by #1746 — held out for separate design attention.

**Resolved**: 2026-08-05 — implementation tracked in #1973.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1972>.
Spec: `specs/case-management.yaml` CM-11-003.
