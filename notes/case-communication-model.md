---
title: Case Communication Model
status: active
kind: guidance
description: >
  Rules for post-creation case messaging: every participant message routes
  through the CASE_MANAGER and state reaches replicas only via CaseLedgerEntry
  broadcast; which resolver to use; Invite/Accept routing; the embargo relay
  (EP-09, ADR-0113), where ledger entries carry state but never ask; the
  delegated-message pattern; and identity-spoofing antipatterns, including
  reading the CASE_MANAGER gate as a sender check (HP-01-006, ADR-0115).
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
  - specs/em-behavior.yaml
  - specs/message-semantics-mapping.yaml
  - specs/rm-behavior.yaml
related_notes:
  - notes/sync-ledger-replication.md
  - notes/case-ledger-authority.md
  - notes/embargo-lifecycle.md
  - notes/participant-embargo-consent.md
  - notes/embargo-default-semantics.md
  - notes/event-driven-control-flow.md
  - notes/participant-case-replica.md
  - notes/outbox.md
  - notes/inbox-orchestration.md
  - notes/use-case-protocol.md
  - notes/protocol-asks.md
  - notes/case-joining.md
  - notes/received-status-authorization.md
  - notes/message-occasion-table.md
  - notes/message-type-reference.md
  - notes/case-proposal.md
  - notes/ownership-transfer.md
  - notes/triggers-test-coverage.md
relevant_packages:
  - vultron/core/use_cases/triggers
  - vultron/core/use_cases/received
  - vultron/core/behaviors/case
  - vultron/core/behaviors/note
  - vultron/core/behaviors/embargo
  - vultron/core/behaviors/sync
---

# Case Communication Model

Requirements: PCR-08, CM-24, HP-01. Decisions: ADR-0021, ADR-0088, ADR-0113, ADR-0115.

---

## The Canonical Communication Flow

Once the CASE_MANAGER has been introduced to the participants, **every case-scoped
participant message goes to the CASE_MANAGER only**:

```text
Participant → CASE_MANAGER → CaseLedgerEntry → Announce(CaseLedgerEntry) → all Participants
```

The CASE_MANAGER validates the activity, updates the case, and commits a
`CaseLedgerEntry`; the commit fans out `Announce(CaseLedgerEntry)`, the only way
participants learn of case-state changes. No participant messages another directly.

| Phase | Rule |
|---|---|
| **Before case creation** | Finder sends `Offer(Report)` directly to Vendor — no CASE_MANAGER exists yet. The only peer-to-peer exception. |
| **Case creation / bootstrap** | `Create(VulnerabilityCase)` introduces the CASE_MANAGER (trust bootstrap, one time). |
| **Inviting a new participant** | See [Invite/Accept Handshake Routing](#inviteaccept-handshake-routing). |
| **After case is active** | Every message from any participant goes to the CASE_MANAGER only. |

**Why:** the CASE_MANAGER is the single writer of case history
([case-ledger-authority](case-ledger-authority.md)). A peer-to-peer message is outside
the log, so replicas cannot be rebuilt from it, the hash chain is incomplete, and the
CASE_MANAGER cannot validate or order it.

---

## Antipattern: the Whole Roster as Recipient List

Never address `to:` from the roster (`case.actor_participant_index` or similar). From a
participant it bypasses the CASE_MANAGER (PCR-08-001); from the CASE_MANAGER it reaches
inert participants (CM-10-004, ADR-0114). A participant sends to the CASE_MANAGER only.
The one stated exception is RK: an addressee of the report's `Offer` sends it to the
reporter directly, case or no case, because it answers that Offer outside the case
(PCR-08-001, RMB-08-003, #4560).
The CASE_MANAGER picks broadcast recipients from
`vultron/core/participants/recipients.py` (CM-10-007): `case_content_recipients()` for
content (active participants not at RM.CLOSED), `ledger_entry_recipients()` for
ledger entries (adds back only a closed participant the entry is about, CM-23-004),
and `invitation_recipients()` for consent Invites.
`test/architecture/test_active_participant_recipient_selection.py` keeps every other
module from listing roster ids for addressing.

---

## Implementation: Resolving the CASE_MANAGER ID

The authority is the participant holding `CVDRole.CASE_MANAGER`. Two resolvers answer
different questions (ARCH-24-005; the full split is in
[case-ledger-authority](case-ledger-authority.md) § "Three Questions That Look Like
One"):

- **`resolve_case_manager_id(case, dl)`** (`vultron/core/participants/authority.py`) —
  "who is the authority?". Needs the case in hand; use it for every gate and authority
  decision. `behaviors/` may import it directly (BTND-04-003).
- **`_find_case_actor_id(dl, case_id)`** — "what address do I route to?". Adds one
  bootstrap path, the `case_manager_id` on a completed `ReportCaseLink`, which answers
  before the replica has a roster. Use it for addressing only (PCR-08-007, PCR-08-008).

Neither consults a URL shape or hosting location: a `.../actors/case-actor` URL has no
protocol meaning (CM-02-013, ADR-0088).

---

## Automatic CaseLedgerEntry + Broadcast Cascade

Every CASE_MANAGER received-side handler that accepts a participant message fires the
cascade itself: guarded commit, then `FanOutLogEntryNode`
(`core/behaviors/sync/nodes/fanout.py`) queues the `Announce` in the CASE_MANAGER
outbox, and each participant's `AnnounceLedgerEntryReceivedUseCase` updates its replica.
The `/actors/{actor_id}/demo/sync-log-entry` endpoint (`routers/demo_triggers.py`) is a
test scaffold only; never part of the normal flow.

---

## Invite/Accept Handshake Routing

The stub Invite creates an **inert** record, which receives no case content
(CM-10-004), so the broadcast cannot deliver the invite; the CASE_MANAGER still owns the
exchange. The full join model is in [case-joining](case-joining.md) (ADR-0114,
ADR-0121).

### Correct Flow

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
     consent row `AGREED` if an embargo is active (CM-11-001)
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

- The Invite's `actor` is the CASE_MANAGER; `attributedTo` MAY carry the case owner
  (PCR-08-007).
- The invitee's `Accept` goes **to the CASE_MANAGER**, not the case owner
  (PCR-08-008). The invitee holds no case yet, but its inbox processes the stub Invite
  on arrival rather than deferring it (`is_deferral_exempt()`, PCR-06-005), so the
  accept and reject triggers find intake's archive record
  (`holds_received_activity()`, `core/services/received_activity.py`) and the reply
  embeds the archived body (`read_received_as_received()`; CLP-10-017, ADR-0149,
  [inbox-orchestration](inbox-orchestration.md)).
- The CASE_MANAGER processes the Accept (PCR-08-009). The same handler runs on any
  actor holding a copy, so its effects sit behind the role gate, and a receiver the gate
  turns away reports `REFUSED` through `case_manager_verdict()`, never `SKIPPED`
  (HP-01-005).
- The handler runs the tree as the **receiving** actor (`resolve_receiving_actor_id()`),
  never as a CASE_MANAGER address looked up from the store (BT-17-006).
- Emit no `RmEngageCaseActivity` for the invitee. Accepting the stub is joining (RM
  stays `RECEIVED`), accepting the full-case Invite is RV; only the participant's own
  `Join(VulnerabilityCase)` records `RM.ACCEPTED` (CM-11-004).

### Implementation Pattern: Role-Gated Emit, CASE_MANAGER Executes

Put the emit inside `create_case_manager_gated_tree`. Never resolve a `case_actor_id`
and compare it with `actor_id`: the authority is a *role*, and an ungated helper is
identity spoofing (CM-24-004). Once gated, the executing actor *is* the CASE_MANAGER and
`dl` is its store, so the activity and its outbox entry land in one store (BT-05-006):
**`dl` determines the queue**, and `add_activity_to_outbox`'s actor argument is only a
log label. A case always has a CASE_MANAGER (CM-24-006): a resolver that finds none
fails; there is no un-delegated fallback (CM-24-008).

---

## Embargo Relay: the Ledger Carries State, It Never Asks (EP-09, ADR-0113)

Every embargo proposal — first or revision — is relayed (EP-09-001). The participant
addresses it to the CASE_MANAGER only. The CASE_MANAGER adjudicates, moves the case
(`NONE → PROPOSED` or `ACTIVE → REVISE`), commits the proposal, then relays one
`Invite(EmbargoEvent)` per participant except the proposer (`actor` the CASE_MANAGER,
`attributedTo` the proposer, `end_time` stamped per CM-28-012), each emission committed.
Participants answer the Invite addressed to them, to the CASE_MANAGER, which commits
each answer; the owner's answer also decides the embargo.

```text
Participant P sends Invite(EmbargoEvent B) → CASE_MANAGER
  CASE_MANAGER: EM NONE → PROPOSED (or ACTIVE → REVISE), commit → Announce to all
  CASE_MANAGER: Invite(B, end_time) → each participant ≠ P, commit → Announce to all
Each participant Q answers Accept/Reject(Invite(B))     → CASE_MANAGER
  CASE_MANAGER: record Q's consent, commit               → Announce to all
Owner answers Accept/Reject(Invite(B))                   → CASE_MANAGER
  CASE_MANAGER: EA/EC activates B or ER/EJ clears/keeps, commit → Announce to all
```

- **A proposer's trigger writes no EM state** unless it holds the CASE_MANAGER role: it
  emits to the manager, records the ask in the pending-assertion store, and its replica
  moves on the announced commit (EP-09-008, EP-09-014).
- **A CASE_MANAGER deciding by trigger** writes, commits, and addresses nothing to
  itself (EP-09-008; `notes/embargo-lifecycle.md` § "Embargo Negotiation Relays
  Through the CASE_MANAGER"). The commit is the EK acknowledgement (EP-09-009).
- **Only the CASE_MANAGER evaluates invite expiry**; replicas learn it from the
  committed entry and never compute it (CM-28-014, ADR-0118).
- **`Announce(CaseLedgerEntry)` is a channel for case state, not a protocol
  interaction.** A proposal or Invite *inside an entry* tells the participant the case's
  state; it answers only an Invite addressed to it (EP-09-003). A non-manager that
  receives a peer's proposal *directly* stores it and writes nothing (RSH-08-003).
- **The owner MAY decide without waiting** for answers and SHOULD wait for some; there
  is no quorum (EP-09-005, EP-09-006). The answers are still the consent records the
  EP-05-001 activation cascade reads.

### What the participant and its replica do

- **The Invite addressed to it.** Store the Invite and its `EmbargoEvent`, then answer
  through the response decision (EMB-15); write no EM or consent state (EP-09-003).
  `CanAnswerEmbargoInviteNode` lets only the sole recipient answer (EP-09-010), and
  only once it holds the case and the embargo; otherwise it keeps the Invite and logs a
  WARNING. `SendEmbargoInviteAnswerNode` fails by raising, so a broken accept never
  falls through to the reject arm.
- **The ledger entries.** Each is applied by one slot of `AnnounceLogEntryReceivedBT`
  (EP-09-007, RSH-08-004). Every slot copies (ADR-0124, CM-23-016): an act's
  entry carries its register step or the row it states, and every other
  consent row those acts change is the CASE_MANAGER's own
  `Create`/`Update(EmbargoConsent)` entry, which the `EmbargoConsent` slot copies, as
  are the rows a withdrawal declines. No slot decides to skip an entry: a
  `Reject` the CASE_MANAGER answers with ET is its `REJECT` step, and the
  CASE_MANAGER's own `Remove` that follows is the `TERMINATE` step, so the
  replica copies both in order (MSM-07-009):

| Entry (`semantic_type`) | Slot | Replica effect |
|---|---|---|
| proposal (`invite_to_embargo_on_case`, not a relay) | `EmbargoProposal` | stores B, copies the `PROPOSE` step (→ `PROPOSED`/`REVISE`), index recorded; the rows follow |
| relayed Invite, re-invites included (same type, `actor` the CASE_MANAGER, `attributedTo` the proposer) | `EmbargoInviteRelay` | stores B, proposer's index; the invitee's `INVITED` row and RSVP deadline follow (CM-28-013) |
| `accept_invite_to_embargo_on_case` | `EmbargoAcceptance` | stores B; copies the `AGREED` row the Accept states, the owner's included; no register change (ADR-0122) |
| `reject_invite_to_embargo_on_case` from a participant | `EmbargoRejection` | stores B; copies the `DECLINED` row the Reject states; no register change |
| `reject_invite_to_embargo_on_case` from the CASE_MANAGER | `EmbargoAbandonment` | copies the `CANCEL` step of the proposal it rejects (EMB-16-001, ADR-0152) |
| `undo_invite_to_embargo_on_case` (the CASE_MANAGER's `Undo` of an Invite it sent) | `EmbargoInviteWithdrawal` | copies the `CANCEL` step of the proposal; in place after the abandonment's first entry (EMB-16-001) |
| `withdraw_from_embargo_on_case` (`Leave(EmbargoEvent)`) | `EmbargoWithdrawal` | stores the embargo if absent; writes no row: each row it declines follows as its own `update_embargo_consent` (MSM-07-010) |
| `create_embargo_consent` / `update_embargo_consent` | `EmbargoConsent` | copies the row the CASE_MANAGER changed, an invitation expiry (`TIMED_OUT`, CM-28-014) and the CASE_MANAGER's own consent change (MSM-07-004) included; a no-op when the seed is past it, else refuses it and holds its Announce |
| `activate_embargo_on_case` (owner's `Accept(EmbargoEvent, target=Case)`) | `EmbargoActivation` | copies the `ACTIVATE` step (B `ACTIVE`, A `SUPERSEDED`) and the owner's `AGREED` row; each `CARRY_OVER` row follows as its own `update_embargo_consent` |
| `reject_embargo_proposal_on_case` (owner's `Reject(EmbargoEvent, target=Case)`) | `EmbargoProposalRejection` | copies the `REJECT` step: B `REJECTED`, EM back to A (or `NONE`) once no proposal is open; no consent. After disclosure the CASE_MANAGER's teardown entry follows in the same act and terminates A (EMB-04-002, MSM-07-009); the replica copies both and decides nothing |
| `remove_embargo_event_from_case` | `EmbargoTeardown` | copies the `TERMINATE` step for the embargo the entry names, with the `CANCEL` of every open proposal (EP-08-004); writes no row (MSM-07-006); an entry naming an embargo not in force here changes nothing |

- A proposal and a relay share one semantic type; `is_relayed_embargo_invite()` reads a
  relay only when `actor` is the case's CASE_MANAGER and `attributedTo` names someone
  else, or names the CASE_MANAGER and the register already holds the embargo decided,
  as for a re-invite (EMB-17-003, ADR-0152). A third party in `attributedTo` from a
  participant is still a proposal (PCR-08-010).
- The CASE_MANAGER never commits a `Reject(Invite(EmbargoEvent))` as its own consent:
  that shape from it is the abandonment, so its own consent change is its
  `Update(EmbargoConsent)` of the row (MSM-07-004).
- Each apply node stores the snapshot's `EmbargoEvent` as it applies the entry,
  so `active_embargo` never names an unreadable record
  (EMB-18-003). A replica without the case skips; one with the case that cannot
  rebuild the embargo fails, blocking persistence (SYNC-12-001).
- `test/architecture/test_embargo_relay_entries_are_replayed.py` is the ratchet;
  `test_embargo_relay_replay.py` drives the cycle across per-actor stores.
  `test/architecture/test_embargo_replica_slots_copy.py` keeps every slot above
  free of lifecycle logic, and every per-actor-store scenario is rebuilt from the
  CASE_MANAGER's ledger into an empty store when it ends
  (`test/support/ledger_rebuild.py`, #4294).

---

## Delegated-Message Pattern

An activity a participant initiates but the protocol requires from the CASE_MANAGER is
sent with `actor` = the CASE_MANAGER and `attributed_to` = the requester (CM-24-001,
CM-24-002), queued in the CASE_MANAGER's outbox (CM-24-004).

- **Every delegated emit calls `delegated_authorship()`**
  (`vultron/core/behaviors/delegated_authorship.py`, CM-24-005); no callsite assigns
  `actor`/`attributed_to` itself. The caller names both identities; the helper looks
  nothing up. `test/architecture/test_delegated_attribution_uses_helper.py` enforces it.
- A trigger resolves the CASE_MANAGER with `resolve_case_manager_id()` and fails when
  there is none (CM-24-006); a received-side node passes `self.actor_id`, which the role
  gate makes the CASE_MANAGER.
- **The delegated emit runs where the CASE_MANAGER is hosted** (ADR-0109). A trigger
  sends the requester's *own* activity to the CASE_MANAGER (the owner's
  `Offer(Actor, Case)` for the invite, CM-17-007; the owner's `Offer(VulnerabilityCase)`
  for an ownership transfer, CM-21-005), and the CASE_MANAGER's received tree emits and
  commits. No trigger executes a tree as the CASE_MANAGER: `BTBridge` raises for an
  executing actor this container does not host (BT-05-005).
- **The CASE_MANAGER never `cc:`s its own emission to itself**: co-hosted, that commits
  the same activity twice.
- For the embargo relay, `resolve_proposer_id()` honours an inbound `attributedTo` only
  when the Invite's `actor` is the CASE_MANAGER, so a participant cannot name a third
  party as proposer.

---

## Antipattern: Identity Spoofing in Received-Side Use Cases

A received-side use case runs in one actor's DataLayer. It MUST NOT build activities or
run BTs with `actor_id` set to another actor (e.g. running the invitee's prioritize
subtree from the owner's store). The CASE_MANAGER records a participant's reply to the
full-case Invite (RV/RI/RC, CM-11-011) as a direct RM write through
`CreateParticipantStatusNode` in its own store, with the participant as subject
and itself as executing actor — no proxy activity (PCR-08-010, ADR-0089). The
stub `Accept` moves no RM state (CM-11-001).

---

## Antipattern: Reading the CASE_MANAGER Gate as a Sender Check

`create_case_manager_gated_tree` and `case_manager_verdict()` check that the
**receiving** actor holds `CVDRole.CASE_MANAGER` (BT-17-001, HP-01-005); they say
nothing about the sender. A gated tree applies an assertion from *any* sender unless
something else checks who sent it.

- **The sender check is a separate guard** (HP-01-006, ADR-0115). Each received use
  case declares its sender entitlement once; the receive-tree factory composes the guard
  from the sender-entitlement module; a failure reports `REFUSED`.
- **A reply is authorized by the ask naming its sender** (the transferee of a recorded
  Offer, the invitee of a recorded Invite), never by the sender's embedded copy of the
  ask (CM-11-017). A replica accepts case-state changes only from the CASE_MANAGER
  (PCR-03-001).
- **The declaration is the whole rule** (HP-01-008, ADR-0129): composed of entitlement
  kinds, possibly any-of, with standing per addressee. A tree adds no narrower sender
  check. Positions within one exchange (invitee, addressee, author) are kinds, never
  `CVDRole` values (HP-01-009). The occasion table will derive its "Sent by" and "Send
  to" columns from these declarations
  ([message-occasion-table](message-occasion-table.md), #4438).

---

## Antipattern: Received-Side Guarded Commit with Foreign CASE_MANAGER ID

Never resolve the CASE_MANAGER's id from the store and run the guarded-commit BT under
it in another actor's DataLayer: the `Announce` is queued under the wrong actor and the
canonical ledger never gets the entry (ADR-0021). Run the tree as the receiving actor
(`resolve_receiving_actor_id()`) and pass the CASE_MANAGER effects as
`create_receive_activity_tree(..., manager_effects=[...])`; the factory wraps them in
the gate, and a received tree never calls the gate itself (BT-17-008). Then map a
skipped gate to `REFUSED` with `case_manager_verdict()` (HP-01-005). See
`vultron/core/behaviors/note/add_note_received_tree.py` for the shape.

The gate is what makes identity correct: role holder, receiving actor and store owner
are one actor or the effects do not run (BT-05-006). The CASE_MANAGER's own inbox
delivery is the only path to a canonical write (CLP-10-001).

**Tests of a gated path MUST seed a `CVDRole.CASE_MANAGER` holder and pass it as
`receiving_actor_id`** (BT-17-005). Without one the skip arm succeeds and the test
passes for the wrong reason.

### Why the `Announce(CaseLedgerEntry)` envelope is not a payload

`Announce(CaseLedgerEntry)` is the replication envelope (SYNC-02-002). A canonical
entry's `payloadSnapshot` is the activity that *triggered* the entry, never the
transport that delivered it, so `announce_case_ledger_entry` MUST NOT appear in
`EXPECTED_SEMANTIC_TYPES` for the canonical log (CLP-10-004, ADR-0021).
