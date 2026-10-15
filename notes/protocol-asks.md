---
title: Protocol Asks and Outstanding-Ask Registers
status: active
kind: plan
tracks:
  - "#2884"
  - "#3188"
  - "#3471"
description: >
  Design guidance for the protocol-ask primitive: asking and terminating rather
  than suspending, conversation-state routing, the outstanding-ask register, ask
  expiry, and processing faults.
related_specs:
  - specs/protocol-asks.yaml
  - specs/case-ledger-processing.yaml
  - specs/event-driven-control-flow.yaml
  - specs/received-status-handling.yaml
  - specs/embargo-policy.yaml
  - specs/case-management.yaml
  - specs/sync-ledger-replication.yaml
related_notes:
  - notes/bt-integration.md
  - notes/bt-pitfalls.md
  - notes/event-driven-control-flow.md
  - notes/received-status-authorization.md
  - notes/case-communication-model.md
  - notes/coordination-agents.md
  - notes/activitystreams-semantics.md
  - notes/embargo-lifecycle.md
  - notes/participant-embargo-consent.md
  - notes/selective-disclosure.md
  - notes/bt-canonical-reference.md
  - notes/call-out-configuration.md
relevant_packages:
  - vultron/core/behaviors
  - vultron/core/models
---

# Protocol Asks and Outstanding-Ask Registers

Normative requirements: `specs/protocol-asks.yaml` (ASK-01 through ASK-08).
Decision record: ADR-0080.

## The one-sentence version

An actor that cannot act on its own authority **emits a request and finishes**.
`SUCCESS` at that point means *I asked*, not *I was told yes*. The reply, when
it comes, starts new work.

## Why there is nothing to suspend

The behavior tree cannot wait for an answer. `BTBridge.execute_tree()` treats
root `RUNNING` as "keep ticking" until `max_iterations` (default 100), then logs
`ERROR` and returns `FAILURE`, and `bt.shutdown()` discards the tree after every
invocation, so there is nothing to resume. Divide the work at the question:
asking is one behavior, acting on the answer is another.

Two mechanisms keep any node from returning `RUNNING` (BT-18-011):

- **Runtime guard at the call-out seam.** Backends are injected from outside the
  repo (BT-23-004), so `SynchronousCallOut`
  (`vultron/core/behaviors/call_out/guard.py`), applied to every factory a
  `CallOutBundle` hands out, raises `CallOutContractError` on `RUNNING`. It is a
  plain `RuntimeError`, not a `VultronError`, so `BTBridge` reports a wiring bug
  (`internal_error=True`), not a protocol `FAILURE`.
- **Static ratchet for in-repo nodes.**
  `test/architecture/test_no_running_status.py` keys on the py_trees `Status`
  enum, so the legacy simulator's `NodeStatus.RUNNING` (`vultron/bt/`) is out of
  scope.

## Conversation-state routing

A gated interaction is **one tree whose first act is to work out where the
conversation stands**. Branches are disjoint, so re-entry never retries
completed work:

```text
GatedAction  (first fitting branch wins)
├── reply in hand      → Accept: do the thing.  Reject: refuse, record, stop.
├── asked, waiting     → stop.  Do not ask again.
├── asked, expired     → re-ask with a fresh deadline, stop.
└── never asked        → record the not-yet state, emit the ask, stop.
```

### Why not just replay the original message

The first run already appended state and committed a ledger entry, and the
CLP-13-001 idempotency guard returns `FAILURE` on the duplicate, so a replayed
tree dies at its first guard before reaching the gate. Disjoint branches never
re-attempt completed work.

### Why not split the tree in two

An ask half and an act half drift apart; one routing tree cannot disagree with
itself. The reply still gets its own tree (its own dispatch key), but the *state*
question lives in one place.

## Prior art: this is built, once, by hand

`create_recommend_actor_to_case_received_tree`
(`vultron/core/behaviors/case/suggest_actor_tree.py`, ADR-0026 / CM-16) is the
reference implementation:

```text
RecommendActorToCaseBT
├── GuardedCommitCaseLedgerEntryBT        — record receipt (CLP-10-006)
└── DuplicateOrFreshSelector
    ├── already a participant   → auto-accept to the recommender
    ├── invite in flight        → auto-accept to the recommender
    ├── owner asked, no answer  → send a Note; do NOT ask twice
    └── fresh                   → evaluate roles, Offer(CaseParticipant) to owner
```

`InviteInFlightNode` and `PendingOfferCaseParticipantNode`
(`case/nodes/suggest_actor/conditions.py`) read open/closed state from the
ledger via `find_protocol_pair`. Two sibling trees handle the `Accept` and the
`Reject`.

`VultronOfferRecord` (`vultron/core/models/offer_record.py`) is the reference
per-ask record: durable, DataLayer-backed, keyed deterministically by
`build_id(offer_id)`, written by the adapter that calls the factory, registered
as wire vocabulary, and usable **before a case exists**. Its justification
(ADR-0035, DL-06-002) is the argument for the register generally — a domain fact
an actor must remember is recorded as core state, not re-derived by re-reading a
stored activity.

**Read both before implementing anything here.** The work is generalising them,
not inventing a mechanism.

## What the working instance is missing

| Gap | Consequence |
|---|---|
| No deadline on the ask | "Pending" has no duration; an unanswered ask is pending forever |
| Nothing enumerates | Deadlines cannot be swept; a Case Owner cannot see decisions they owe |
| Bespoke throughout | Every node is hand-written for one flow; the next instance costs the same |

The third gap is why `RequireCaseOwnerApprovalNode` is still a deny-always stub.

## Rules worth internalising

**Authority comes from the stored ask, never the reply** (ASK-01-004). Read the
granted roles from the stored `Offer`, not from the `CaseParticipant` embedded in
the received `Accept`, or the accepting actor can escalate what it grants itself.

**Expiry consequence is per ask kind and is not configurable.** Admitting a
participant stays useful when authorized late; adopting a case status does not —
by then the case state the decision was made against has moved on. Whether a
late reply authorizes is a protocol rule fixed in the spec (ASK-03-003), because
two actors disagreeing about it is divergence in canonical case state, not a
deployment preference. The *duration* is tunable per actor precisely because it
travels on the wire in `end_time`, so both parties read the same number off the
same object.

**The register never authorizes.** Two questions, two sources:

| Question | Answered by |
|---|---|
| What am I waiting on? What do I owe? | the outstanding-ask register |
| Was this authorized? | the case ledger, always |

A gate reads the ledger and never the register (ASK-02-004), so a corrupted or
rebuilt register cannot permit an action. Same division as
`actor_participant_index` (fast index) versus the canonical record (authority).

**One register class, two instances.** The create / close-on-named-event /
time-out lifecycle, its reaping and its enumeration are written once
(ASK-04-007). The durable ask register may block; `PendingAssertionStore` is
ephemeral, is forgotten on restart *by design*, and may never block (CLP-06-002,
CLP-06-005). CLP-11-002 forbids unifying the registers, not sharing the
lifecycle — and both already share `ProtocolPair` as their key type
(CLP-11-003).

Ephemerality is a safety property, not an oversight: a suppressor entry that
survived a restart would suppress a re-send that *should* happen. Forgetting
fails **open** (you might duplicate, which idempotency handles) rather than
**closed** (you stay silent forever).

**An ask may only park an action whose not-yet state is legitimate.** Nothing
suspends, so the case sits in the pre-authorization state for the whole
deadline. `add_participant_status_tree` already satisfies this — the
participant's claim is appended, and only *adoption as canonical* is gated
(RSH-01). An action with no representable not-yet state must be refused rather
than asked about (ASK-02-005).

**The embargo Invite is an ask kind, and a relayed ask belongs to the relayer.**
`Invite(EmbargoEvent)` is closed by `Accept`/`Reject` from the invitee, carries
its deadline in `end_time` (CM-28-012), and a late reply is still honoured
(EMB-17) — stale expiry, not void (ASK-03-007). Under the embargo relay
(EP-09, ADR-0113) the CASE_MANAGER emits one Invite per participant with itself
as `actor` and the proposer in `attributedTo`, so the manager records those as
its own outstanding asks; the proposer records only its proposal to the manager
(ASK-04-010). `find_protocol_pair`'s one-open-request-per-type assumption does
not survive N simultaneous Invites of one event type — the ask-kind registry
(#2884) is where that gets fixed, not a per-call-site workaround.

**The pending-assertion store has a second client.** Embargo triggers that do
not hold the CASE_MANAGER role emit their proposal, answer or termination to the
manager, write no EM state (EP-09-008), and record it in the pending-assertion
store. Every asker records through `record_pending_assertion()` and checks
repeats through `suppressed_repeat_reason()`
(`vultron/core/models/pending_assertion.py`, ASK-04-008), including the P/X/A
cascade's teardown ask. An embargo repeat carries a fresh activity id, so its
entry carries a `subject_id` (the offered terms, the answered proposal, or the
ended embargo) and a repeat inside the window queues nothing. The store stays a
duplicate suppressor that never holds case state (CLP-06-002). An announced commit
clears the entry (SYNC-11-003); a refused proposal is never committed, so only
the CASE_MANAGER's received `Reject` of it closes the entry
(`close_refused_embargo_proposal`, `received/_pending_refusal.py`).

**Asks are visible to the whole case.** An ask is an ordinary recorded entry and
replicates normally (ASK-06-001), so a stalled decision is visible to
participants. Consequently an ask must carry nothing undisclosable to them
(ASK-06-002); private rationale goes in a `Note` directed to one participant,
the way the refusal notice is a `Reject` directed to one (CLP-05-001). Delivering the *fact* of an ask while
directing its *detail* would need redaction with proofs, which Vultron does not have
(design: `notes/selective-disclosure.md`); committing a stub instead would break CLP-02-003 and CLP-07-012.

## Expiry has no clock, and that is deliberate

Time passing delivers no message, so nothing runs a tree unprompted. Two
mechanisms, neither a loop inside core:

1. **Opportunistic** — the next entry into the tree observes the expired ask
   (ASK-05-001). Frequently sufficient: for a lost `Accept(CaseProposal)` the
   peer's own retry is the clock, and that retry is also what lets the answerer
   recover (CP-05-006).
2. **A Sentinel seam** — a general-purpose `reap-expired-asks` trigger
   (ASK-05-002). A Sentinel works on the call-in surface and has no BT call-out
   point (`notes/coordination-agents.md`), so reaping belongs to an external
   watcher, not to core. The endpoint also makes expiry testable causally, not by
   elapsed time (EDF-06-001).

Reaping never re-emits (ASK-05-004), mirroring CLP-06-005: a timeout is a
signal, not an instruction to retry. Only the tree knows whether the action is
still wanted.

## Processing faults

`Create(ProcessingFault)` tells an **authenticated** sender that its message
could not be processed. It is one object type, not a port of the simulator's
RE/EE/CE/GE/GI message family, which ADR-0049 declined.

Design points that are easy to get wrong:

- **`Create`, not `Reject`.** `Reject` presupposes something rejectable;
  unreadable traffic provides no such object. `Create(<minted object>)` is the
  established idiom (`Create(CaseProposal)`).
- **A dedicated object type, not a reason field** (SE-08-003).
- **A pointer, never a required echo.** When a payload fails validation, a typed
  copy of it cannot be constructed, because constructing it is what failed.
  Echoing sender-supplied content is also a reflection hazard.
- **Authenticated senders only** (ASK-07-002). Explaining a parse failure to a
  stranger is a parser oracle, and an unauthenticated identity is not a
  trustworthy reply address.
- **RFC 9457 Problem Details, with failure classes as URIs** minted in the
  Vultron namespace (VM-10-001, ADR-0069). The canonical list is then
  dereferenceable and extensible without a schema change.
- **No implementation diagnostics** (ASK-07-006). Faults replicate to every
  participant. Stack traces and parser internals go in the actor's own log,
  governed by `specs/structured-logging.yaml`.

### What is recorded, and what is not

Three things that look alike and are not:

| Situation | Where it lands |
|---|---|
| I read your assertion, understood it, refuse it | refusal notice (`Reject`) to you alone, not recorded (CLP-05-001, CLP-05-002) |
| I read your ask, my answer is no | `Reject` reply, ordinary recorded entry |
| I could not read what you sent | a fault; the unreadable message is **not** recorded |

The third is not a decision — nothing was adjudicated, so there is no legible
assertion to snapshot, and CLP-03-002 already excludes unrouteable inbound from
the ledger. Do **not** reach for the refusal notice here: it answers an
assertion that was *understood and refused*.

The **fault statement itself** is different. "B could not process A's message" is
a true, legible statement about a message that arrived, so it is recorded as an
ordinary entry (ASK-07-008) and it explains a subsequent retransmission. It is
not per-actor observability content, so CLP-07-004 is unaffected: the *fact* of a
fault is protocol history; the *diagnosis* is not.

## Pitfalls

**Every BT node outbox write goes through one seam:**
`_EmitSingleActivityBase._emit_through_seam()` (`vultron/core/behaviors/helpers.py`);
subclasses override `_call_factory()` / `_on_success()`. The ASK-04-008
correlation hook and the OX-14-001 dead-letter link belong there.
`test/architecture/test_no_direct_outbox_append_in_bt_node_update.py` forbids a
direct `outbox_append` in a node's `update()`. The `Create(ProcessingFault)` NACK
(`_FaultMixin.emit_processing_fault()`) uses a separate outbox path.

**Delivery receipt is not agreement.** "Your message arrived" and "I agree to
what your message said" are different layers and must not be conflated.
The ledger keeps
recording what an actor decided and observed at the time it happened
(OX-14-002) — gating a commit on delivery would make an actor's own history
hostage to the network, invert CLP-10-006's ordering, and raise an unanswerable
partial-delivery question. What was missing is the *link* from a dead-lettered
activity to the entry claiming its event happened (OX-14-001).

**`Question` is not the verb for an ask.** `as_Question` is an
`IntransitiveActivity` with no `object`, so the thing asked about has nowhere to
live and `find_protocol_pair`, which keys on an object ID, cannot pair it. Use
`Offer` for "may I". Do not use `Question` to make a choice either: competing
embargo terms resolve as sequential `Invite`s in earliest-expiration order (EP-08,
ADR-0100). The one remaining `as_Question`, `bootstrap_replay_question_activity`
(CBT-03-004), has no pattern, semantics or handler, so it is emitted and dropped;
it is not a precedent (#3471). Design a request/response exchange as a protocol
ask.

**Do not relax a gate to make a blocked path proceed** (RSH-07-005).
`STATUS_AUTHORIZATION_PERMISSIVE` is for trusted-participant and demo
deployments; using it to route around an unreachable gate turns a protocol
guarantee into a configuration posture.
