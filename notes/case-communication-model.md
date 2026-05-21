---
title: Case Communication Model
status: active
description: >
  Canonical communication model for post-case-creation participant messaging:
  all participant messages route through the Case Actor exclusively, and all
  state updates propagate via CaseLogEntry broadcast. Captures the routing
  rule, its rationale, common antipatterns, and BT implementation guidance.
related_specs:
  - specs/participant-case-replica.yaml
  - specs/sync-log-replication.yaml
  - specs/case-log-processing.yaml
  - specs/case-management.yaml
related_notes:
  - notes/sync-log-replication.md
  - notes/case-log-authority.md
  - notes/event-driven-control-flow.md
  - notes/participant-case-replica.md
  - notes/two-actor-demo.md
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
Participant → Case Actor → CaseLogEntry → Announce(CaseLogEntry) → all Participants
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
   the activity, updates local case state, and commits a `CaseLogEntry`
   recording the outcome (accepted or rejected).

3. **Automatic broadcast**: The `CaseLogEntry` commit automatically triggers
   `Announce(CaseLogEntry)` to all case participants. This is the **only**
   mechanism by which participants learn of accepted case-state changes.

---

## Scope: When Does This Rule Apply?

| Phase | Rule |
|---|---|
| **Before case creation** | Finder sends `Offer(Report)` directly to Vendor — no Case Actor exists yet. This direct peer message is the **only** exception. |
| **Case creation / bootstrap** | Vendor sends `Create(VulnerabilityCase)` to Finder to introduce the Case Actor. This is the trust-bootstrap handshake (one-time exception). |
| **After case is active** | ALL subsequent messages from any participant go to the Case Actor only. No direct peer messaging. |

---

## Why This Model

The Case Actor is the single writer of authoritative shared history
(see `notes/case-log-authority.md`). If participants send messages
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
broadcast** (when the Case Actor fans out a `CaseLogEntry` to all
participants). It is wrong on the **participant sender** side.

---

## Implementation: Resolving the Case Actor ID

The Case Actor is the participant with `CVDRole.CASE_MANAGER`. To resolve
its actor ID from a known case:

```python
from vultron.core.states.roles import CVDRole

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

## Automatic CaseLogEntry + Broadcast Cascade

Every Case Actor received-side handler that accepts a participant message
MUST trigger the cascade automatically — not via a manual demo endpoint.
The expected flow:

1. Case Actor inbox receives participant activity.
2. Case Actor's received-side use case (or BT) processes the assertion.
3. On acceptance: `commit_log_entry()` → `_fan_out_log_entry()` (queues
   `Announce(CaseLogEntry)` to all participants via Case Actor outbox).
4. `OutboxMonitor` drains the Case Actor outbox → delivers to each
   participant's inbox.
5. Participant's `AnnounceLogEntryReceivedUseCase` (`received/sync.py`)
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

## Known Implementation Gaps (as of 2026-05-21)

| Gap | Location | Status |
|---|---|---|
| Notes trigger sends to all participants | `triggers/note.py:102` | Open — tracked in impl issues |
| Embargo triggers send to all participants | `triggers/embargo.py:399,472,589,657,773` | Open |
| Engage/defer-case triggers send to all participants | `triggers/case.py:84,132` | Open |
| No sender-side BTs | All of the above | Open — BT refactor issue |
| Auto CaseLogEntry cascade not wired to all received handlers | Multiple | Open |

See GitHub issues under parent concern #593.
