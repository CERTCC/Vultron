---
title: Protocol Asks and Outstanding-Ask Registers
status: active
description: >
  Design guidance for the protocol-ask primitive: asking and terminating rather
  than suspending, conversation-state routing, the outstanding-ask register, ask
  expiry, and processing faults.
related_specs:
  - specs/protocol-asks.yaml
  - specs/case-ledger-processing.yaml
  - specs/event-driven-control-flow.yaml
  - specs/received-status-handling.yaml
related_notes:
  - notes/bt-integration.md
  - notes/event-driven-control-flow.md
  - notes/received-status-authorization.md
  - notes/case-communication-model.md
  - notes/coordination-agents.md
relevant_packages:
  - vultron/core/behaviors
  - vultron/core/models
---

# Protocol Asks and Outstanding-Ask Registers

Normative requirements: `specs/protocol-asks.yaml` (ASK-01 through ASK-08).
Decision record: ADR-0080. Source: CONCERN-2829 (planning group G01).

## The one-sentence version

An actor that cannot act on its own authority **emits a request and finishes**.
`SUCCESS` at that point means *I asked*, not *I was told yes*. The reply, when
it comes, starts new work.

## Why there is nothing to suspend

The recurring instinct is to make the behavior tree wait: return `RUNNING`, hold
the tree, resume it when the answer arrives. The framework cannot do this, and
the evidence is unambiguous:

- `BTBridge.execute_tree()` ticks in `while iteration < max_iterations`
  (default 100) and treats root `RUNNING` as "keep ticking". Exhausting the loop
  logs `ERROR` and returns `FAILURE`.
- `finally: bt.shutdown()` discards the tree at the end of every invocation, so
  there is no instance to resume.
- `grep -r "return Status.RUNNING" vultron/` returns **nothing**. EDF-04-002
  used to require `RUNNING` while awaiting input; it had zero implementations,
  and any node that had complied would have busy-looped and then failed.

So the design that looked blocked on a missing framework feature was never on
that path. Dividing the work at the question — asking is one behavior, acting on
the answer is another — needs no suspension at all.

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

Tempting and wrong: on reply, feed the triggering activity back through the
inbox so the same tree runs again and passes the gate. The first run already
appended state and committed a ledger entry, and CLP-13-001 requires an
idempotency guard that detects a duplicate to return `FAILURE` and write
nothing. The replayed tree therefore dies at its first guard, before reaching
the gate. Disjoint branches avoid this by never attempting the completed work in
the first place.

### Why not split the tree in two

Also tempting: an ask half and an act half, with the reply handler invoking the
act half. It works, but two halves drift; one routing tree cannot disagree with
itself. The reply still gets its own tree (it is a different inbound message
with its own dispatch key) — but the *state* question lives in one place.

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

The third gap is why `RequireCaseOwnerApprovalNode` is a deny-always stub. The
mechanism was known; generalising it was never done, so the second instance cost
more than anyone wanted to pay.

## Rules worth internalising

**Authority comes from the stored ask, never the reply.** ADR-0026 states this
for participant roles and calls it a security boundary: read the roles from the
stored `Offer`, not from the `CaseParticipant` embedded in the received
`Accept`, or the accepting actor can escalate what it grants itself. ASK-01-004
generalises it to every ask.

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

**Asks are visible to the whole case.** An ask is an ordinary recorded entry and
replicates normally (ASK-06-001), so a stalled decision is visible to
participants. Consequently an ask must carry nothing undisclosable to them
(ASK-06-002); private rationale goes in a directed `Note`, which CLP-05-001
already establishes as a delivery shape. Delivering the *fact* of an ask while
directing its *detail* would need redaction with proofs — `notes/stub-objects.md`
describes redaction as future work, and committing a stub instead would break
CLP-02-003 and CLP-07-012.

## Expiry has no clock, and that is deliberate

Time passing delivers no message, so nothing runs a tree unprompted. Two
mechanisms, neither a loop inside core:

1. **Opportunistic** — the next entry into the tree observes the expired ask
   (ASK-05-001). Frequently sufficient: for a lost `Accept(CaseProposal)` the
   peer's own retry is the clock, and that retry is also what lets the answerer
   recover (CP-05-006).
2. **A Sentinel seam** — a general-purpose `reap-expired-asks` trigger
   (ASK-05-002). Per `notes/coordination-agents.md`, a Sentinel *"operates
   exclusively on the call-in surface"* and **has no BT call-out point**, so
   reaping belongs to an external watcher, not to core. The same endpoint makes
   expiry testable causally instead of by elapsed time, which EDF-06-001
   requires.

Reaping never re-emits (ASK-05-004), mirroring CLP-06-005: a timeout is a
signal, not an instruction to retry. Only the tree knows whether the action is
still wanted.

## Processing faults

`Create(ProcessingFault)` tells an **authenticated** sender that its message
could not be processed. This discharges the deferral ADR-0049 recorded — that
ADR declined to port the RE/EE/CE/GE/GI message family from the simulation but
explicitly asked that sender notification be *"designed on its own merits"*
later. One fault object type is not that family, so ADR-0049's decision stands.

Design points that are easy to get wrong:

- **`Create`, not `Reject`.** `Reject` presupposes something rejectable;
  unreadable traffic provides no such object. `Create(<minted object>)` is the
  established idiom (`Create(CaseProposal)`).
- **A dedicated object type, not a reason field.** SE-08-003 prefers a dedicated
  object type over field-level discrimination — the lesson CONCERN-2322 taught.
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
| I read your assertion, understood it, refuse it | ledger, `disposition="rejected"` |
| I read your ask, my answer is no | `Reject` reply, ordinary recorded entry |
| I could not read what you sent | a fault; the unreadable message is **not** recorded |

The third is not a decision — nothing was adjudicated, so there is no legible
assertion to snapshot, and CLP-03-002 already excludes unrouteable inbound from
the ledger. Do **not** reach for `disposition="rejected"` here: that mechanism
records an assertion that was *understood and refused*.

The **fault statement itself** is different. "B could not process A's message" is
a true, legible statement about a message that arrived, so it is recorded as an
ordinary entry (ASK-07-008) and it explains a subsequent retransmission. It is
not per-actor observability content, so CLP-07-004 is unaffected: the *fact* of a
fault is protocol history; the *diagnosis* is not.

## Pitfalls

**There is no general shared emit path yet.** `outbox_append` is called from
roughly twenty modules, and at least four private emit helpers exist
independently:

```text
case/nodes/actor.py:142                        _emit()
case/nodes/accept_invite.py:141                _emit_activity()
case/nodes/delegation.py:213                   _emit()
case/nodes/suggest_actor/accept_offer.py:53    _emit()
```

`_FaultMixin.emit_processing_fault()` (added in #2989) covers the
`Create(ProcessingFault)` NACK path specifically, but the general problem —
consolidating all activity emissions through a single point — remains open.
Registration that each call site must remember to perform will be forgotten
(ASK-04-008), so a general shared path is still a prerequisite for the
CONCERN-2657 correlation work. It **cannot** live in the AS2 factory:
factories are wire-layer, have no DataLayer, and wire must not import core. It
belongs on the core side, alongside the shared BT node base classes in
`behaviors/helpers.py`.

**Delivery receipt is not agreement.** "Your message arrived" and "I agree to
what your message said" are different layers and must not be conflated.
CONCERN-2657 is the former; everything else here is the latter. The ledger keeps
recording what an actor decided and observed at the time it happened
(OX-14-002) — gating a commit on delivery would make an actor's own history
hostage to the network, invert CLP-10-006's ordering, and raise an unanswerable
partial-delivery question. What was missing is the *link* from a dead-lettered
activity to the entry claiming its event happened (OX-14-001).

**`Question` is not the verb for an authorization ask.** `as_Question` exists and
is used for polls (`choose_preferred_embargo`, `oneOf` over embargo options), but
it is an `IntransitiveActivity` — it has **no `object`**, as the code comment
says outright. The thing being asked about has nowhere to live, and
`find_protocol_pair` keys on an object ID. Use `Offer` for "may I", `Question`
for "which one".

**Do not relax a gate to make a blocked path proceed** (RSH-07-005).
`STATUS_AUTHORIZATION_PERMISSIVE` is for trusted-participant and demo
deployments. Using it to route around an unreachable gate converts a protocol
guarantee back into a configuration posture, which is the defect CONCERN-2092
filed.
