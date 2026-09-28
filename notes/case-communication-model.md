---
title: Case Communication Model
status: active
description: >
  Canonical communication model for post-case-creation participant messaging:
  all participant messages route through the CASE_MANAGER exclusively, and all
  state updates propagate via CaseLedgerEntry broadcast. Captures the routing
  rule, its rationale, common antipatterns, and BT implementation guidance.
related_specs:
  - specs/architecture.yaml
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

Once a case is created and the actor enacting `CVDRole.CASE_MANAGER` has been
introduced to all participants, **all case-scoped participant messages MUST flow
through the CASE_MANAGER exclusively**. The canonical flow is:

```text
Participant → CASE_MANAGER → CaseLedgerEntry → Announce(CaseLedgerEntry) → all Participants
```

No participant may send a case-scoped message directly to another
participant. The CASE_MANAGER is the single intermediary and single writer
of authoritative case history.

### Three-Phase Breakdown

1. **Participant → CASE_MANAGER**: The originating participant sends
   `Add(Note)`, `Add(ParticipantStatus)`, `Offer(Embargo)`, or any other
   case-scoped activity addressed **only** to the CASE_MANAGER
   (`to: [case_actor_id]`).

2. **CASE_MANAGER processes + commits**: On receipt, the CASE_MANAGER validates
   the activity, updates local case state, and commits a `CaseLedgerEntry`
   recording the outcome (accepted or rejected).

3. **Automatic broadcast**: The `CaseLedgerEntry` commit automatically triggers
   `Announce(CaseLedgerEntry)` to all case participants. This is the **only**
   mechanism by which participants learn of accepted case-state changes.

---

## Scope: When Does This Rule Apply?

| Phase | Rule |
|---|---|
| **Before case creation** | Finder sends `Offer(Report)` directly to Vendor — no CASE_MANAGER exists yet. This direct peer message is the **only** exception. |
| **Case creation / bootstrap** | Vendor sends `Create(VulnerabilityCase)` to Finder to introduce the CASE_MANAGER. This is the trust-bootstrap handshake (one-time exception). |
| **Inviting a new participant** | See [Invite/Accept Handshake Routing](#inviteaccept-handshake-routing) below. The CASE_MANAGER sends `Invite` on the owner's behalf and processes `Accept`. |
| **After case is active** | ALL subsequent messages from any participant go to the CASE_MANAGER only. No direct peer messaging. |

---

## Why This Model

The CASE_MANAGER is the single writer of authoritative shared history
(see `notes/case-ledger-authority.md`). If participants send messages
directly to each other:

- Content arrives outside the canonical log, so replicas cannot
  be rebuilt deterministically from the log alone.
- The hash chain is not authoritative because state-changing events
  are not all recorded in it.
- The CASE_MANAGER cannot enforce validation, reject malformed assertions,
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
# ❌ WRONG — sends to all participants directly, bypassing the CASE_MANAGER
addressees = case_addressees(case, actor_id)   # [vendor, finder]  (excludes caller)
activity = add_note_to_case_activity(
    note=note, target=case_id, actor=actor_id, to=addressees
)
```

```python
# ✅ CORRECT — send only to the CASE_MANAGER
case_manager_id = _resolve_case_manager_id(case, dl)  # only the CASE_MANAGER actor
activity = add_note_to_case_activity(
    note=note, target=case_id, actor=actor_id, to=[case_manager_id]
)
```

`case_addressees()` is still correct for the CASE_MANAGER's **outbound
broadcast** (when the CASE_MANAGER fans out a `CaseLedgerEntry` to all
participants). It is wrong on the **participant sender** side.

---

## Implementation: Resolving the CASE_MANAGER ID

The authority is the participant holding `CVDRole.CASE_MANAGER`. To resolve
its actor ID from a known case:

```python
from vultron.core.participants.authority import resolve_case_manager_id
```

This extraction landed in PR #3219 under ADR-0088. `resolve_case_manager_id`
is the canonical implementation used by all sender-side trigger use cases.

**Which of the two resolvers to reach for.** They answer different questions,
and picking the wrong one is how hosting signals crept back in before
(ARCH-24-005; the full three-way split is in
[case-ledger-authority](case-ledger-authority.md) § "Three Questions That Look
Like One"):

- **`resolve_case_manager_id(case, dl)`** — "am I / who is the authority?"
  Needs a `VulnerabilityCase` in hand. Use it for every gate and every
  authority decision. It lives in the neutral layer, so `behaviors/` may import
  it directly (no `behaviors → use_cases` hop, BTND-04-003).
- **`_find_case_actor_id(dl, case_id)`** — "what address do I route to?" Takes a
  case *id* and adds one bootstrap path: the `trusted_case_actor_id` recorded on
  a completed `ReportCaseLink`, which answers before the local replica has a
  roster to read. Use it for addressing (`to:` / `cc:`) — PCR-08-007,
  PCR-08-008.

Neither consults a URL shape or a `Service` object's hosting location. ADR-0088
removed both, along with the `is_case_actor_identity` predicate: an ordinary
participant enacting `CASE_MANAGER` *is* the authority and *is* the address, and
a `.../actors/case-actor` URL is a provisioning convenience with no protocol
meaning (CM-02-013, ARCH-24-004).

---

## Automatic CaseLedgerEntry + Broadcast Cascade

Every CASE_MANAGER received-side handler that accepts a participant message
MUST trigger the cascade automatically — not via a manual demo endpoint.
The expected flow:

1. CASE_MANAGER inbox receives participant activity.
2. CASE_MANAGER's received-side use case (or BT) processes the assertion.
3. On acceptance: `commit_log_entry()` → `_fan_out_log_entry()` (queues
   `Announce(CaseLedgerEntry)` to all participants via the CASE_MANAGER outbox).
4. `OutboxMonitor` drains the CASE_MANAGER outbox → delivers to each
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
  ├── ConstructActivityNode       # builds the AS2 activity addressed to CASE_MANAGER
  └── QueueToOutboxNode           # adds to actor outbox
```

Until BTs are implemented, the interim fix is to ensure all trigger use
cases use `_resolve_case_manager_id()` instead of `case_addressees()` as
the recipient when building outbound participant activities.

---

## Invite/Accept Handshake Routing

Adding a new participant to an active case uses `RmInviteToCaseActivity` /
`RmAcceptInviteToCaseActivity`. Because the invitee is not yet a participant,
the standard CASE_MANAGER → broadcast model cannot be used to deliver the invite.
However, the CASE_MANAGER MUST still be the authoritative actor in the exchange.

### Correct Flow

```text
Case Owner triggers SvcInviteActorToCaseUseCase
  → CASE_MANAGER sends Invite(actor=case_actor_id, attributedTo=case_owner_id)
    → Invitee's inbox

Invitee sends Accept(Invite, actor=invitee_id, to=[case_actor_id])
  → CASE_MANAGER's inbox (NOT the case owner's inbox)

CASE_MANAGER's AcceptInviteActorToCaseReceivedUseCase:
  1. Creates CaseParticipant at RM.VALID
  2. Records RM VALID→ACCEPTED inline (Accept(Invite) IS the engage signal)
  3. Emits Announce(VulnerabilityCase) to invitee
  4. Commits CaseLedgerEntry → Announce(CaseLedgerEntry) broadcast
```

### Key Rules

- `actor` on `RmInviteToCaseActivity` MUST be the **CASE_MANAGER's ID**.
  `attributedTo` MAY carry the case owner's ID (PCR-08-007).
- The invitee's `Accept` MUST be addressed **to the CASE_MANAGER**,
  not to the case owner (PCR-08-008).
- The CASE_MANAGER (not the case owner) MUST process the Accept and
  record the invitee's RM transition (PCR-08-009).
- No `RmEngageCaseActivity` is emitted on behalf of the invitee.
  `Accept(Invite)` is semantically equivalent to engaging, so the
  separate engage step is redundant.

### Implementation Pattern: Role-Gated Emit, CASE_MANAGER Executes

**Updated by ADR-0073 / CM-24-004.** The emit must sit inside a composite gated
on the executing actor holding `CVDRole.CASE_MANAGER` for the case
(`create_case_manager_gated_tree`). Code MUST NOT instead resolve a
`case_actor_id` and compare it against `actor_id`: the authority is a *role* held
in the case, its holder may be any Actor type, and ungated the same helper is
identity spoofing — any actor reaching it could emit as the CASE_MANAGER.

Once the emit is role-gated the executing actor *is* the case manager, so
`dl` already belongs to it and the activity and its outbox entry land in one store
by construction (BT-05-006). That is also why `add_activity_to_outbox`'s first
argument is now only a log label: **`dl` determines the queue**, and
`record_outbox_item` — which enqueued against an explicit `actor_id`, bypassing
`dl`'s scope — is gone, because there is no unscoped `dl` for it to compensate
for.

```python
# Inside a CASE_MANAGER-gated composite, so `actor_id` is the case manager
# and `dl` is its own store.
activity_id = trigger_activity.invite_actor_to_case(
    invitee_id=invitee_id,
    case_id=case_id,
    actor=actor_id,                # ← the role holder sends (CM-24-001)
    attributed_to=requester_id,    # ← originating participant (CM-24-002)
    to=[invitee_id],
)
add_activity_to_outbox(actor_id, activity_id, dl)   # ← dl *is* the manager's store
```

When a case has no `CVDRole.CASE_MANAGER` participant the delegation channel does
not exist: the Activity is sent directly by the requesting participant, with
`actor` set to it and `attributed_to` set to `None` (CM-24-003).

---

## Delegated-Message Pattern

Some case-scoped Activities are logically initiated by a participant but MUST
be sent under the CASE_MANAGER's identity — because the protocol requires the
CASE_MANAGER to be the recognised sender.  This is the **delegated-message
pattern** (CM-24-001 through CM-24-005):

```text
Requesting actor calls trigger: <trigger-name>
  → Trigger use case _prepare():
      self._actor_id     = case_actor_id      ← CASE_MANAGER sends (CM-24-001)
      self._attributed_to = requesting_actor_id  ← attribution preserved (CM-24-002)
      # When unresolvable: self._actor_id = requesting_actor_id,
      #                     self._attributed_to = None (CM-24-003)
  → BT runs under the CASE_MANAGER's identity → activity queued in its outbox (CM-24-004)

Recipient receives Activity:
  actor        = case_actor_id       ← the CASE_MANAGER as sender
  attributed_to = requesting_actor_id  ← who initiated the action
```

### Reference Implementation

Use `_prepare_delegated_context()` (`triggers/_helpers.py`) as the canonical
implementation.  All delegated-emit trigger use cases MUST call this helper
(CM-24-005).  When the BT tree also needs `case_actor_id` separately (e.g.
for the `cc:` routing in the invite flow), resolve it with a second
`_find_case_actor_id()` call after the helper:

```python
# Delegated-message contract (CM-24-001..003)
self._actor_id, self._attributed_to = _prepare_delegated_context(
    self._dl, self._case.id_, requesting_actor_id
)
# case_actor_id needed separately when BT tree requires it (e.g. invite cc:)
self._case_actor_id = _find_case_actor_id(self._dl, self._case.id_)
```

### Delegated Flows (Exhaustive)

| Trigger use case | Notes |
|---|---|
| `SvcInviteActorToCaseUseCase` | ✅ uses `_prepare_delegated_context()` |
| `SvcOfferCaseOwnershipTransferUseCase` | ✅ fixed in #2173 |
| Other trigger use cases | audit complete — no other delegated-emit callsites |

### Shared-Helper Requirement (CM-24-005)

All delegated-message trigger use cases MUST use a shared helper to enforce
the pattern.  No callsite may independently reconstruct `actor/attributed_to`
assignment.  See `specs/case-management.yaml` CM-24-005 for the normative
requirement.

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
# ✅ CORRECT — the CASE_MANAGER advances the invitee's RM state through the sole
# writer, in its own DataLayer, attributing the write to the invitee — no proxy
# activity and no spoofed invitee BT (ADR-0089):
BTBridge(datalayer=dl).execute_with_setup(
    CreateParticipantStatusNode(
        actor_id=invitee_id,        # subject of the write
        rm_state=RM.ACCEPTED,
        vf_state=None, d_state=None, pxa_state=None,
    ),
    actor_id=case_actor_id,         # the executing actor (owner of this store)
    case_id=case_id,
)
```

The `Accept(Invite)` message is the invitee's engage decision. The CASE_MANAGER
records that decision as a direct RM state update, without emitting a proxy
`RmEngageCaseActivity` (PCR-08-010).

---

## Antipattern: Received-Side Guarded Commit with Foreign CASE_MANAGER ID

A subtler form of identity spoofing appears when a received-side use case
resolves the CASE_MANAGER's ID from the DataLayer and then executes the
guarded-commit BT under that foreign ID — even though the active DataLayer
belongs to a different actor (e.g., the vendor actor). This was the pattern
in `note.py` and `embargo.py` before ADR-0021 was established.

```python
# ❌ WRONG — resolves a foreign actor ID and runs BT under that identity
case_actor_id = _find_case_actor_id(self._dl, case_id)   # foreign ID
BTBridge(datalayer=self._dl).execute_with_setup(         # vendor's DL
    tree=create_guarded_commit_case_ledger_entry_tree(case_id),
    actor_id=case_actor_id,   # ← spoofed: vendor's DL, the CASE_MANAGER's identity
    ...
)
```

The problem: `self._dl` is the **vendor actor's** DataLayer (since the use case
is running in the vendor's inbox), but `actor_id=case_actor_id` causes the BT
to emit `Announce(CaseLedgerEntry)` as if authored by the CASE_MANAGER. The
outbox entry is queued under the wrong actor, and the CASE_MANAGER's canonical
ledger never receives it.

The correct pattern (from `status.py`'s `_commit_log_cascade_bt`) is a strict
pre-flight guard that only proceeds when the receiving actor IS the CASE_MANAGER:

```python
# ✅ CORRECT — pre-flight guard; only commits when receiving actor holds CASE_MANAGER
receiving_actor_id = request.receiving_actor_id
case_actor_id = _find_case_actor_id(self._dl, case_id)

if receiving_actor_id != case_actor_id:
    return   # not the CASE_MANAGER — skip commit entirely

# Now safe: receiving_actor_id == case_actor_id, so DL matches identity
BTBridge(datalayer=self._dl).execute_with_setup(
    tree=create_guarded_commit_case_ledger_entry_tree(case_id),
    actor_id=receiving_actor_id,   # ← correct: same as active DL
    ...
)
```

The pre-flight guard is what makes the identity correct. When a non-CASE_MANAGER
receives the same activity (relay copy to finder, vendor's own inbox), the
guard fires and the commit is skipped. The CASE_MANAGER's own inbox delivery —
which arrives because the trigger tree emitted to `case_manager_id`
(CLP-10-001) — is the only path to a canonical write.

### Why the `Announce(CaseLedgerEntry)` envelope is not a payload

`Announce(CaseLedgerEntry)` is the replication wire envelope the CASE_MANAGER
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
