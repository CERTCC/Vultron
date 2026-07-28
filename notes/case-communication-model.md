---
title: Case Communication Model
status: active
description: >
  Canonical communication model for post-case-creation participant messaging:
  all participant messages route through the Case Actor exclusively, and all
  state updates propagate via CaseLedgerEntry broadcast. Captures the routing
  rule, its rationale, common antipatterns, and BT implementation guidance.
related_specs:
  - specs/participant-case-replica.yaml
  - specs/sync-ledger-replication.yaml
  - specs/case-ledger-processing.yaml
  - specs/case-management.yaml
related_notes:
  - notes/sync-ledger-replication.md
  - notes/case-ledger-authority.md
  - notes/event-driven-control-flow.md
  - notes/participant-case-replica.md
  - notes/fv-demo.md
relevant_packages:
  - vultron/core/use_cases/triggers
  - vultron/core/use_cases/received
  - vultron/core/behaviors/case
  - vultron/core/behaviors/note
---

# Case Communication Model

**Source**: 2026-05-21 grill-me session. Normative requirements: `PCR-08`.

---

## The Canonical Communication Flow

Once a case is created and the Case Actor has been introduced to all
participants, **all case-scoped participant messages MUST flow through
the Case Actor exclusively**. The canonical flow is:

```text
Participant → Case Actor → CaseLedgerEntry → Announce(CaseLedgerEntry) → all Participants
```

No participant may send a case-scoped message directly to another
participant. The Case Actor is the single intermediary and single writer
of authoritative case history.

### Three-Phase Breakdown

1. **Participant → Case Actor**: The originating participant sends
   `Add(Note)`, `Add(ParticipantStatus)`, `Offer(Embargo)`, or any other
   case-scoped activity addressed **only** to the Case Actor
   (`to: [case_actor_id]`).

2. **Case Actor processes + commits**: On receipt, the Case Actor validates
   the activity, updates local case state, and commits a `CaseLedgerEntry`
   recording the outcome (accepted or rejected).

3. **Automatic broadcast**: The `CaseLedgerEntry` commit automatically triggers
   `Announce(CaseLedgerEntry)` to all case participants. This is the **only**
   mechanism by which participants learn of accepted case-state changes.

---

## Scope: When Does This Rule Apply?

| Phase | Rule |
|---|---|
| **Before case creation** | Finder sends `Offer(Report)` directly to Vendor — no Case Actor exists yet. This direct peer message is the **only** exception. |
| **Case creation / bootstrap** | Vendor sends `Create(VulnerabilityCase)` to Finder to introduce the Case Actor. This is the trust-bootstrap handshake (one-time exception). |
| **Inviting a new participant** | See [Invite/Accept Handshake Routing](#inviteaccept-handshake-routing) below. The Case Actor sends `Invite` on the owner's behalf and processes `Accept`. |
| **After case is active** | ALL subsequent messages from any participant go to the Case Actor only. No direct peer messaging. |

---

## Why This Model

The Case Actor is the single writer of authoritative shared history
(see `notes/case-ledger-authority.md`). If participants send messages
directly to each other:

- Content arrives outside the canonical log, so replicas cannot
  be rebuilt deterministically from the log alone.
- The hash chain is not authoritative because state-changing events
  are not all recorded in it.
- The Case Actor cannot enforce validation, reject malformed assertions,
  or maintain consistent ordering.
- Demo and protocol analysis become unreliable because the actual
  message flow diverges from the specified model.

---

## Antipattern: `case_addressees()` as Recipient List

`case_addressees(case, excluding_actor_id)` returns **all** actor IDs in
the case participant index except the caller. Using this as the sole
`to:` recipient list for outbound participant activities is incorrect
after case creation:

```python
# ❌ WRONG — sends to all participants directly, bypassing Case Actor
addressees = case_addressees(case, actor_id)   # [vendor, finder]  (excludes caller)
activity = add_note_to_case_activity(
    note=note, target=case_id, actor=actor_id, to=addressees
)
```

```python
# ✅ CORRECT — send only to the Case Actor
case_manager_id = _resolve_case_manager_id(case, dl)  # only the CASE_MANAGER actor
activity = add_note_to_case_activity(
    note=note, target=case_id, actor=actor_id, to=[case_manager_id]
)
```

`case_addressees()` is still correct for the Case Actor's **outbound
broadcast** (when the Case Actor fans out a `CaseLedgerEntry` to all
participants). It is wrong on the **participant sender** side.

---

## Implementation: Resolving the Case Actor ID

The Case Actor is the participant with `CVDRole.CASE_MANAGER`. To resolve
its actor ID from a known case:

```python
from vultron.enums.roles import CVDRole

def _resolve_case_manager_id(case, dl) -> str | None:
    for p_id in case.actor_participant_index.values():
        p = dl.read(p_id)
        roles = getattr(p, "case_roles", [])
        if CVDRole.CASE_MANAGER in roles:
            manager_actor_id = getattr(p, "attributed_to", None)
            return str(manager_actor_id) if manager_actor_id else None
    return None
```

This pattern already exists in `SvcAddParticipantStatusUseCase` (which
correctly routes to the Case Actor only) and should be extracted as a
shared helper used by all sender-side trigger use cases.

---

## Automatic CaseLedgerEntry + Broadcast Cascade

Every Case Actor received-side handler that accepts a participant message
MUST trigger the cascade automatically — not via a manual demo endpoint.
The expected flow:

1. Case Actor inbox receives participant activity.
2. Case Actor's received-side use case (or BT) processes the assertion.
3. On acceptance: `commit_log_entry()` → `_fan_out_log_entry()` (queues
   `Announce(CaseLedgerEntry)` to all participants via Case Actor outbox).
4. `OutboxMonitor` drains the Case Actor outbox → delivers to each
   participant's inbox.
5. Participant's `AnnounceLedgerEntryReceivedUseCase` (`received/sync.py`)
   processes the entry and updates the local replica.

The `vultron/adapters/driving/fastapi/routers/demo_triggers.py`
`sync-log-entry` endpoint exists only as a
**test scaffold** for manually injecting log entries during demo
verification. It MUST NOT be part of the normal message flow — the
cascade must fire automatically as a consequence of any accepted
participant message.

---

## BT Implementation Guidance

Sender-side trigger use cases (`SvcAddNoteToCaseUseCase`,
`SvcAddParticipantStatusUseCase`, embargo triggers, etc.) currently contain
routing logic and activity-construction code that belongs in Behavior Trees.
The correct architecture:

```text
TriggerUseCase.execute()
  └── Sets blackboard context (actor_id, case_id, payload)
  └── Ticks BT

SenderBT (Sequence)
  ├── ResolveCaseManagerNode      # looks up CASE_MANAGER actor ID
  ├── ConstructActivityNode       # builds the AS2 activity addressed to Case Actor
  └── QueueToOutboxNode           # adds to actor outbox
```

Until BTs are implemented, the interim fix is to ensure all trigger use
cases use `_resolve_case_manager_id()` instead of `case_addressees()` as
the recipient when building outbound participant activities.

---

## Invite/Accept Handshake Routing

Adding a new participant to an active case uses `RmInviteToCaseActivity` /
`RmAcceptInviteToCaseActivity`. Because the invitee is not yet a participant,
the standard CaseActor → broadcast model cannot be used to deliver the invite.
However, the Case Actor MUST still be the authoritative actor in the exchange.

### Correct Flow

```text
Case Owner triggers SvcInviteActorToCaseUseCase
  → Case Actor sends Invite(actor=case_actor_id, attributedTo=case_owner_id)
    → Invitee's inbox

Invitee sends Accept(Invite, actor=invitee_id, to=[case_actor_id])
  → Case Actor's inbox (NOT the case owner's inbox)

Case Actor's AcceptInviteActorToCaseReceivedUseCase:
  1. Creates VultronParticipant at RM.VALID
  2. Records RM VALID→ACCEPTED inline (Accept(Invite) IS the engage signal)
  3. Emits Announce(VulnerabilityCase) to invitee
  4. Commits CaseLedgerEntry → Announce(CaseLedgerEntry) broadcast
```

### Key Rules

- `actor` on `RmInviteToCaseActivity` MUST be the **Case Actor's ID**.
  `attributedTo` MAY carry the case owner's ID (PCR-08-007).
- The invitee's `Accept` MUST be addressed **to the Case Actor**,
  not to the case owner (PCR-08-008).
- The Case Actor (not the case owner) MUST process the Accept and
  record the invitee's RM transition (PCR-08-009).
- No `RmEngageCaseActivity` is emitted on behalf of the invitee.
  `Accept(Invite)` is semantically equivalent to engaging, so the
  separate engage step is redundant.

### Implementation Pattern: Owner Triggers, Case Actor Executes

`SvcInviteActorToCaseUseCase` resolves the Case Actor ID, constructs the
Invite with `actor=case_actor_id`, and places it in the **Case Actor's
outbox** — not the case owner's outbox:

```python
case_actor_id = _find_case_actor_id(dl, case_id)
activity_id = trigger_activity.invite_actor_to_case(
    invitee_id=invitee_id,
    case_id=case_id,
    actor=case_actor_id,           # ← Case Actor sends
    attributed_to=actor_id,        # ← Case Owner attribution
    to=[invitee_id],
)
add_activity_to_outbox(case_actor_id, activity_id, dl)   # ← Case Actor outbox
```

---

## Antipattern: Identity Spoofing in Received-Side Use Cases

A received-side use case runs in one actor's DataLayer context. It MUST NOT
construct activities or run BTs with `actor_id` set to a **different** actor.

```python
# ❌ WRONG — runs invitee's BT from the owner's DataLayer context
bridge = BTBridge(datalayer=self._dl, ...)         # owner's DL
tree = create_prioritize_subtree(actor_id=invitee_id)  # invitee's identity
bridge.execute_with_setup(tree, actor_id=invitee_id)   # spoofed actor
```

```python
# ✅ CORRECT — inline transition; no BT, no spoofed emit
participant.append_rm_state(RM.ACCEPTED, actor=invitee_id, context=case_id)
dl.save(participant)
```

The `Accept(Invite)` message is the invitee's engage decision. The Case Actor
records that decision as a direct RM state update, without emitting a proxy
`RmEngageCaseActivity` (PCR-08-010).

---

## Antipattern: Received-Side Guarded Commit with Foreign CaseActor ID

A subtler form of identity spoofing appears when a received-side use case
resolves the CaseActor's ID from the DataLayer and then executes the
guarded-commit BT under that foreign ID — even though the active DataLayer
belongs to a different actor (e.g., the vendor actor). This was the pattern
in `note.py` and `embargo.py` before ADR-0021 was established.

```python
# ❌ WRONG — resolves a foreign actor ID and runs BT under that identity
case_actor_id = _find_case_actor_id(self._dl, case_id)   # foreign ID
BTBridge(datalayer=self._dl).execute_with_setup(         # vendor's DL
    tree=create_guarded_commit_case_ledger_entry_tree(case_id),
    actor_id=case_actor_id,   # ← spoofed: vendor's DL, CaseActor's identity
    ...
)
```

The problem: `self._dl` is the **vendor actor's** DataLayer (since the use case
is running in the vendor's inbox), but `actor_id=case_actor_id` causes the BT
to emit `Announce(CaseLedgerEntry)` as if authored by the CaseActor. The
outbox entry is queued under the wrong actor, and the CaseActor's canonical
ledger never receives it.

The correct pattern (from `status.py`'s `_commit_log_cascade_bt`) is a strict
pre-flight guard that only proceeds when the receiving actor IS the CaseActor:

```python
# ✅ CORRECT — pre-flight guard; only commits when receiving actor IS CaseActor
receiving_actor_id = request.receiving_actor_id
case_actor_id = _find_case_actor_id(self._dl, case_id)

if receiving_actor_id != case_actor_id:
    return   # not the CaseActor — skip commit entirely

# Now safe: receiving_actor_id == case_actor_id, so DL matches identity
BTBridge(datalayer=self._dl).execute_with_setup(
    tree=create_guarded_commit_case_ledger_entry_tree(case_id),
    actor_id=receiving_actor_id,   # ← correct: same as active DL
    ...
)
```

The pre-flight guard is what makes the identity correct. When a non-CaseActor
receives the same activity (relay copy to finder, vendor's own inbox), the
guard fires and the commit is skipped. The CaseActor's own inbox delivery —
which arrives because the trigger tree emitted to `case_manager_id`
(CLP-10-001) — is the only path to a canonical write.

### Why the `Announce(CaseLedgerEntry)` envelope is not a payload

`Announce(CaseLedgerEntry)` is the replication wire envelope the CaseActor
uses to broadcast canonical entries to participants (SYNC-02-002). It cannot
appear as the `payloadSnapshot` of a canonical entry because the snapshot
captures the protocol activity that *triggered* the entry, not the transport
mechanism that *delivered* it. Think of it as a postcard (the protocol
activity) placed inside a binder envelope (the `CaseLedgerEntry`) that is
then mailed to all recipients (the `Announce` broadcast). The envelope is
never its own contents.

This is why `announce_case_ledger_entry` MUST NOT appear in
`EXPECTED_EVENT_TYPES` for the canonical case-actor log (CLP-10-004).

See ADR-0021 for the full decision record.

---

## Known Implementation Gaps

| Gap | Location | Status |
|---|---|---|
| Notes trigger sends to all participants | `triggers/note.py:102` | Open |
| Embargo triggers send to all participants | `triggers/embargo.py` | Open |
| Engage/defer-case triggers send to all participants | `triggers/case.py:84,132` | Open |
