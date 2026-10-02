---
title: Case Communication Model
status: active
description: >
  Canonical communication model for post-case-creation participant messaging:
  all participant messages route through the CASE_MANAGER exclusively, and all
  state updates propagate via CaseLedgerEntry broadcast. Captures the routing
  rule, its rationale, common antipatterns, BT implementation guidance, and the
  embargo revision relay (EP-09, ADR-0113): ledger entries carry state to
  replicas but never set a parse-and-respond expectation.
related_specs:
  - specs/architecture.yaml
  - specs/embargo-policy.yaml
  - specs/participant-case-replica.yaml
  - specs/sync-ledger-replication.yaml
  - specs/case-ledger-processing.yaml
  - specs/case-management.yaml
  - specs/behavior-tree-integration.yaml
  - specs/handler-protocol.yaml
  - specs/protocol-asks.yaml
related_notes:
  - notes/sync-ledger-replication.md
  - notes/case-ledger-authority.md
  - notes/embargo-lifecycle.md
  - notes/participant-embargo-consent.md
  - notes/embargo-default-semantics.md
  - notes/event-driven-control-flow.md
  - notes/participant-case-replica.md
  - notes/fv-demo.md
  - notes/outbox.md
  - notes/inbox-orchestration.md
  - notes/use-case-protocol.md
  - notes/protocol-asks.md
  - notes/case-joining.md
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

## Antipattern: the Whole Roster as Recipient List

The retired `case_addressees(case, excluding_actor_id)` returned **all**
actor IDs in the case participant index except the caller. Two things were
wrong with using any such roster-wide list as `to:`:

1. On the **participant sender** side it bypasses the CASE_MANAGER
   (PCR-08-001/002).
2. On the **CASE_MANAGER broadcast** side it reaches inert participants —
   those that have not accepted the stub Invite, or are not SIGNATORY to an
   active embargo (CM-10-004, ADR-0114).

```python
# ❌ WRONG — sends to all participants directly, bypassing the CASE_MANAGER
addressees = list(case.actor_participant_index)   # [vendor, finder]
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

The CASE_MANAGER's **outbound broadcast** picks its recipients from
`vultron/core/participants/recipients.py` (CM-10-007): case content goes to
`case_content_recipients()` (active participants only), and a consent Invite
goes to `invitation_recipients()` (every participant not at RM.CLOSED, inert
ones included). `test/architecture/test_active_participant_recipient_selection.py`
keeps every other module from listing roster actor IDs for addressing.

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
  case *id* and adds one bootstrap path: the `case_manager_id` recorded on
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
cases use `_resolve_case_manager_id()` instead of a roster-wide list as
the recipient when building outbound participant activities.

---

## Invite/Accept Handshake Routing

Adding a new participant to an active case uses `RmInviteToCaseActivity` /
`RmAcceptInviteToCaseActivity`. The stub Invite creates the invitee's
participant record, but the record is **inert** — it receives no case content
(CM-10-004) — so the standard CASE_MANAGER → broadcast model cannot deliver the
invite. The CASE_MANAGER MUST still be the authoritative actor in the exchange.
The join model is ADR-0114 and ADR-0070; the full flow is in
[case-joining.md](case-joining.md).

### Correct Flow

This is the target model (CM-11, ADR-0114, ADR-0070). The code still creates
the participant on `Accept(Invite)`; the implementation issues spawned from
issue #4006 move it.

```text
Case Owner triggers SvcInviteActorToCaseUseCase
  → Case Owner sends its own Offer(Actor, Case, suggestedRoles)
    → CASE_MANAGER's inbox (CM-17-007, ADR-0109)
  → CASE_MANAGER's recommend-actor tree takes the owner-direct branch, since
    the recommender holds CVDRole.CASE_OWNER (it does not forward the Offer)
  → CASE_MANAGER creates the invitee's CaseParticipant (inert: RM.RECEIVED,
    VF v for a vendor, consent INVITED if an embargo is active) and commits
    the creation to the ledger (CM-11-006)
  → CASE_MANAGER sends Invite(Actor, VulnerabilityCaseStub,
    actor=case_actor_id, attributedTo=case_owner_id), commits it in the
    emitting tree, no cc: (CM-17-006) → invitee's inbox

Invitee sends Accept(Invite(stub), actor=invitee_id, to=[case_actor_id])
  → CASE_MANAGER's inbox (NOT the case owner's inbox)

AcceptInviteActorToCaseReceivedUseCase, at every receiver of a copy:
  1. Commits the receipt CaseLedgerEntry (guarded; CLP-10-006)
  2. CASE_MANAGER gate (create_case_manager_gated_tree, BT-17-001):
     a non-manager stops here and the handler reports REFUSED (HP-01-005)
  3. Activates the existing record: RM stays RECEIVED, VF V for a vendor,
     consent SIGNATORY if an embargo is active (CM-11-001) — joining, not a
     judgement of the case
  4. Emits Announce(VulnerabilityCase) to the participant and replays the
     prior ledger to it (CM-11-008)
  5. Queues the full-case Invite(Actor, VulnerabilityCase) after the last
     replayed entry, carrying its ledger tail position (CM-11-010)

Participant replies to the full-case Invite, carrying its own ledger position:
  Accept (RV) → RM.VALID · TentativeReject (RI) → RM.INVALID ·
  Reject (RC) → RM.CLOSED (CM-11-011)

Reject(Invite(stub)) instead of Accept → RM.CLOSED on the kept, inert record
(CM-11-007)
```

### Key Rules

- `actor` on `RmInviteToCaseActivity` MUST be the **CASE_MANAGER's ID**.
  `attributedTo` MAY carry the case owner's ID (PCR-08-007).
- The invitee's `Accept` MUST be addressed **to the CASE_MANAGER**,
  not to the case owner (PCR-08-008). The invitee holds no case yet, so its
  inbox usually defers the Invite until the bootstrap the Accept brings; the
  accept and reject triggers read the Invite through `read_received_activity()`
  (`core/use_cases/_helpers.py`), which takes intake's archive record or that
  deferred copy (CLP-10-017; see
  [inbox-orchestration](inbox-orchestration.md)).
- The CASE_MANAGER (not the case owner) MUST process the Accept and
  record the invitee's RM transition (PCR-08-009). The same handler runs on
  any actor holding a copy, so admitting, announcing and backfilling sit
  behind the role gate; a receiver the gate turns away reports `REFUSED`
  through `not_case_manager_refusal()`, never `SKIPPED` (HP-01-005, #3752).
- The handler runs the tree as the **receiving** actor only
  (`resolve_receiving_actor_id()`), never as a CASE_MANAGER address looked
  up from the store: that ran the tree under a foreign identity and let the
  gate pass for a store that was not the manager's (BT-17-006, #3823).
- No `RmEngageCaseActivity` is emitted on behalf of the invitee. Accepting
  the stub Invite is *joining* — RM stays `RECEIVED` (CM-11-001) — and
  accepting the full-case Invite is RV (`RM.VALID`, CM-11-011). Neither is
  engagement: only the participant's own `Join(VulnerabilityCase)` records
  `RM.ACCEPTED` (CM-11-004).

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

A case always has a `CVDRole.CASE_MANAGER` participant (CM-24-006), so there is
no un-delegated path: a resolver that finds no holder fails rather than sending
directly. The CM-24-003 fallback (`actor` = requester, `attributed_to = None`)
is retired; #3964 removes it from `_prepare_delegated_context()`.

---

## Embargo Relay: the Ledger Carries State, It Never Asks (EP-09, ADR-0113)

The case Invite above is one instance of a general shape, and every embargo
proposal — the first one for a case or a revision — is the second. A
participant addresses its proposal to the CASE_MANAGER only (PCR-08-001). The
CASE_MANAGER adjudicates it, moves the canonical case (`NONE → PROPOSED` or
`ACTIVE → REVISE`), commits the proposal, and *then* relays it: one
`Invite(EmbargoEvent)` per participant except the proposer, `actor` the
CASE_MANAGER, `attributedTo` the proposer (CM-24), `end_time` stamped by the
manager (CM-28-012), each emission committed. Participants answer the Invite
addressed to them, to the CASE_MANAGER; the CASE_MANAGER commits each answer;
the owner's answer also decides the embargo. Replicas reconstruct every step
from the ledger (RSH-08-004).

```text
Participant P sends Invite(EmbargoEvent B) → CASE_MANAGER
  CASE_MANAGER: EM NONE → PROPOSED (or ACTIVE → REVISE), commit → Announce to all
  CASE_MANAGER: Invite(B, end_time) → each participant ≠ P, commit → Announce to all
Each participant Q answers Accept/Reject(Invite(B))     → CASE_MANAGER
  CASE_MANAGER: record Q's consent, commit               → Announce to all
Owner answers Accept/Reject(Invite(B))                   → CASE_MANAGER
  CASE_MANAGER: EA/EC activates B or ER/EJ clears/keeps, commit → Announce to all
```

The proposer's own trigger writes no EM state unless the proposer holds the
CASE_MANAGER role: it emits, records the ask in the pending-assertion store,
and its replica moves on the announced commit (EP-09-008). The manager's
commit is also the acknowledgement the behavioural specs call EK (EP-09-009).

The rule this pins down, because it kept getting mixed up: **an
`Announce(CaseLedgerEntry)` is a channel for case state, not a protocol
interaction.** A participant that sees a proposal or an Invite *inside a ledger
entry* is being told the case's state; it is not being asked anything, and it
answers only an Invite addressed to it (EP-09-003). Conversely, a non-manager
that receives a peer's proposal *directly* is seeing a misrouting: it stores the
activity and writes nothing (RSH-08-003). Neither path gets parse-and-respond
handling. The protocol interactions the behavioural specs define (EV/EC/EJ)
still happen — relayed — and the ledger records them; it does not replace them.

The owner MAY decide without waiting for answers and SHOULD wait for some to
gauge consensus; the protocol defines no quorum (EP-09-005, EP-09-006). The
Invites still matter under fiat because their answers are the consent records
the EP-05-001 activation cascade reads. Full write-up:
`notes/embargo-lifecycle.md` § "Embargo Negotiation Relays Through the
CASE_MANAGER".

**There is no "no CASE_MANAGER" arm.** Both case-creation paths register a
holder at birth and delegation hands the role on, so the resolver finding nobody
means a corrupt roster, not a topology. CM-24-003's "send directly" fallback is
superseded by CM-24-006; a resolver that finds no holder fails.

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
      # No holder found: raise (CM-24-006) — the CM-24-003 "send directly"
      #                   fallback is retired (#3964)
  → BT runs under the CASE_MANAGER's identity → activity queued in its outbox (CM-24-004)

Recipient receives Activity:
  actor        = case_actor_id       ← the CASE_MANAGER as sender
  attributed_to = requesting_actor_id  ← who initiated the action
```

### Reference Implementation

Use `_prepare_delegated_context()` (`triggers/_helpers.py`) as the canonical
implementation.  All delegated-emit trigger use cases MUST call this helper
(CM-24-005):

```python
# Delegated-message contract (CM-24-001, CM-24-002, CM-24-006)
self._actor_id, self._attributed_to = _prepare_delegated_context(
    self._dl, self._case.id_, requesting_actor_id
)
```

**The delegated emit runs where the CASE_MANAGER is hosted** (CM-24-004,
ADR-0109).  A container emits only as actors it hosts, so a trigger on a
container that does not host the CASE_MANAGER does not run the tree as the
CASE_MANAGER.  It sends the requesting participant's *own* activity to the
CASE_MANAGER — the owner's direct invite is the owner's recommend-actor
`Offer(Actor, Case)` (CM-17-007) — and the CASE_MANAGER's received tree performs the delegated emit
and commits the entry in that tree.  The CASE_MANAGER never addresses a `cc:`
copy of its own emission to itself; the former self-copy compensated for a
foreign-container emit and committed the same Invite twice when the two were
co-hosted (#2996).  For the invite, #3821 landed this: `SvcInviteActorToCaseUseCase`
(`core/use_cases/triggers/actor.py`) sends the owner's Offer, and the owner-direct
branch of `create_recommend_actor_to_case_received_tree` (`suggest_actor_tree.py`)
emits and commits the Invite.  #3822 lands the ownership-transfer trigger; until it
does, that trigger still runs the delegated emit locally.

### Delegated Flows (Exhaustive)

| Trigger use case | Notes |
|---|---|
| `SvcInviteActorToCaseUseCase` | ✅ emits nothing delegated since #3821: it sends the owner's own Offer, and the delegated emit is the CASE_MANAGER's owner-direct branch of `create_recommend_actor_to_case_received_tree`, a received-side emit under `create_case_manager_gated_tree` (CM-17-007) |
| `SvcOfferCaseOwnershipTransferUseCase` | ✅ fixed in #2173 |
| `invite_to_embargo_on_case_tree` — CASE_MANAGER arm (EP-09-002) | ✅ built in #3913 (ADR-0113) — a *received*-side delegated emit, as CM-24-004 allows: `RelayEmbargoInviteToEachNode` relays `Invite(EmbargoEvent)` to every participant except the proposer with `actor=CASE_MANAGER`, `attributed_to=proposer`, each emission committed in the emitting tree; the proposer comes from `resolve_proposer_id()` (the Invite's `actor`, or its `attributedTo` when the proposal was itself relayed) |
| Other trigger use cases | audit complete — no other delegated-emit callsites |

### Shared-Helper Requirement (CM-24-005)

All delegated-message trigger use cases MUST use a shared helper to enforce
the pattern.  No callsite may independently reconstruct `actor/attributed_to`
assignment.  See `specs/case-management.yaml` CM-24-005 for the normative
requirement.

The one *received*-side delegated emit, the embargo relay
(`RelayEmbargoInviteToEachNode`, #3913), does not call
`_prepare_delegated_context()`: that is a trigger use-case helper a BT node
may not import (BTND-04-003), and its "no CASE_MANAGER, send directly" arm is
what ADR-0113 retires (#3964).  The node holds the CM-24-001/002 invariants
structurally instead — it runs only under `create_case_manager_gated_tree`, so
`actor` is the role holder by construction, and `attributed_to` is the proposer
the manager adjudicated (`resolve_proposer_id()`, which honours an inbound
`attributedTo` only when the Invite's `actor` is itself the CASE_MANAGER, so a
participant cannot name a third party as proposer).  A second received-side
delegated emit should extract a shared received-side helper rather than repeat
this reasoning.

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
# ✅ CORRECT — the CASE_MANAGER advances the participant's RM state through the
# sole writer, in its own DataLayer, attributing the write to the participant —
# no proxy activity and no spoofed participant BT (ADR-0089):
BTBridge(datalayer=dl).execute_with_setup(
    CreateParticipantStatusNode(
        actor_id=invitee_id,        # subject of the write
        rm_state=RM.VALID,          # Accept of the full-case Invite (CM-11-011)
        vf_state=None, d_state=None, pxa_state=None,
    ),
    actor_id=case_actor_id,         # the executing actor (owner of this store)
    case_id=case_id,
)
```

A reply to the full-case Invite is the participant's judgement of the case
(RV/RI/RC, CM-11-011; ADR-0070). The CASE_MANAGER records it as a direct RM
state update, without emitting a proxy activity on the participant's behalf
(PCR-08-010). The stub `Accept` moves no RM state at all (CM-11-001).

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

The correct pattern runs the tree as the receiving actor and lets the tree
decide, through the sanctioned role gate, whether that actor may act
(BT-17-001, BTND-07-005). Code MUST NOT instead compare the receiving actor
against a `case_actor_id` looked up from the store (CM-24-004): the authority
is a *role* held in the case, not an address.

```python
# ✅ CORRECT — the tree runs as the receiving actor; the gate decides
tree = create_receive_activity_tree(
    ...,
    effect_nodes=[
        create_case_manager_gated_tree(
            name="AttachNoteIfCaseManager",
            case_id=case_id,
            children=[AttachNoteNode(...), ...],
        ),
    ],
)
result = BTBridge(datalayer=self._dl).execute_with_setup(
    tree,
    actor_id=resolve_receiving_actor_id(self._dl, request.receiving_actor_id),
    activity=request,
)
verdict = verdict_from_bt(tree, result, label="AddNoteToCaseBT")
if verdict.disposition is HandlerDisposition.APPLIED:
    if (r := not_case_manager_refusal(tree, self._dl, case_id)) is not None:
        verdict = r   # REFUSED: not the manager, or no case / no manager here
```

The gate is what makes the identity correct: the role holder, the receiving
actor and the store owner are one actor or the effects do not run (BT-05-006).
When a non-CASE_MANAGER receives the same activity (relay copy to finder,
vendor's own inbox), the gate's skip arm succeeds so the tree still succeeds,
and the handler turns that skip into `REFUSED` — the message was the manager's
to act on and reached the wrong party (HP-01-005, #3752). The CASE_MANAGER's
own inbox delivery — which arrives because the trigger tree emitted to
`case_manager_id` (CLP-10-001) — is the only path to a canonical write.

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
