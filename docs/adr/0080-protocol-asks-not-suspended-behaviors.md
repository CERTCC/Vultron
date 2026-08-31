---
status: accepted
date: 2026-08-31
deciders: Allen D. Householder
consulted: Claude Opus 5
informed: []
---

# Asking Permission Is a Protocol Message, Not a Suspended Behavior

## Context and Problem Statement

Several independently filed Concerns bottom out on the same missing mechanism:
core has no established way for an actor to request something it lacks the
authority to do on its own, wait for an answer that arrives later, and act on
that answer when it comes.

The most visible symptom is `RequireCaseOwnerApprovalNode`
(`vultron/core/behaviors/call_out/nodes.py`), the DETERMINISTIC default for both
authorization gates of ADR-0046. It returns `Status.FAILURE` unconditionally.
ADR-0076 specifies its intended behavior as an `Offer`/`Accept`/`Reject`
round-trip with the Case Owner, but records no mechanism for hosting that
exchange, and CONCERN-2812 filed the resulting gap: *"the Offer/Accept/Reject
round-trip requires a BT-hosted async request/response pattern that does not
exist in the framework."*

Three findings reframed the problem during planning:

1. **The framework cannot host in-tree suspension, and never has.**
   `BTBridge.execute_tree()` ticks in a `while iteration < max_iterations` loop
   (default 100), treats root `RUNNING` as "keep ticking", logs `ERROR` and
   returns `FAILURE` when the loop is exhausted, and discards the tree in a
   `finally: bt.shutdown()`. Meanwhile no node anywhere in `vultron/` returns
   `Status.RUNNING`. EDF-04-002 requires an external decision node to return
   `RUNNING` while awaiting input; that requirement has zero implementations,
   and any node that complied would busy-loop and then fail.

2. **The mechanism already exists in production, built by hand, once.**
   `create_recommend_actor_to_case_received_tree`
   (`vultron/core/behaviors/case/suggest_actor_tree.py`, ADR-0026 / CM-16)
   records receipt, then routes through a Selector whose branches are disjoint:
   already a participant, invite in flight, Case Owner already asked and not yet
   answered, or fresh. The fresh branch forwards `Offer(CaseParticipant)` to the
   Case Owner and stops. Two further trees handle the `Accept` and the `Reject`.
   `InviteInFlightNode` and `PendingOfferCaseParticipantNode` read open/closed
   state from the case ledger via `find_protocol_pair`.

3. **The durable per-ask record also exists, built by hand, once.**
   `VultronOfferRecord` (`vultron/core/models/offer_record.py`) is a
   DataLayer-backed core record keyed deterministically off an Offer's ID, written
   by the adapter that calls the factory, registered as wire vocabulary, and
   usable before a case exists. Its justification (ADR-0035, DL-06-002) is that a
   domain fact an actor must remember MUST be recorded as core state rather than
   recovered by re-reading a stored activity.

So the question was never *how* to host an asynchronous exchange. It was: why
does each instance cost a bespoke implementation, and what is the shape that
makes the next one cheap?

## Decision Drivers

- Nothing can suspend, so any design premised on suspension is unimplementable
  in this framework and would require replacing the execution model
- The pattern recurs (status adoption, embargo teardown, participant admission,
  ownership transfer, case proposal) and each instance has so far been rebuilt
  from scratch
- The current conservative default is not merely unfinished — it is
  unsatisfiable, so the authorization model of ADR-0046 and ADR-0076 cannot be
  reached by any pathway
- An asker that never learns its request failed stalls silently and
  indefinitely; silence is the failure mode common to every member Concern
- A Case Owner has no surface on which to discover that a decision is waiting
  for them, so approval can only happen by accident
- CLP-11-001 and DL-06-002 already contradict each other on whether outstanding
  protocol state is derived from the ledger or recorded as core state

## Considered Options

1. **Suspend the behavior tree** — implement `RUNNING` propagation, hold the
   tree across invocations, and resume it when the reply arrives.
2. **Replay the original message** — on reply, feed the triggering activity back
   through the inbox so the same tree runs again and passes the gate.
3. **Split each gated tree in two** — an ask half and an act half, with the
   reply handler invoking the act half as a shared subtree.
4. **Ask and stop; route on conversation state** (chosen) — the ask is an
   ordinary protocol message that terminates the behavior successfully; each
   interaction is one tree whose first act is to determine where the
   conversation stands, with disjoint branches per state.

## Decision Outcome

Chosen option: **ask and stop; route on conversation state.**

An actor that cannot act on its own authority **emits `Offer(Proposal)` and
terminates successfully**. `SUCCESS` means *I asked*, not *I was told yes*.
Nothing suspends, because the work is divided at the question rather than
paused there: asking is one complete behavior, and acting on the answer is
another, begun by the answer's arrival.

Each gated interaction is **one tree that routes on conversation state before
doing anything**:

```text
GatedAction  (first fitting branch wins)
├── reply in hand      → Accept: perform the action.  Reject: refuse, record, stop.
├── asked, waiting     → stop.  Do not ask again.
├── asked, expired     → re-ask with a fresh deadline, stop.
└── never asked        → record the not-yet state, emit Offer(Proposal), stop.
```

Because the branches are disjoint, re-entry never retries completed work. This
is why option 2 fails: a replayed tree re-executes its pre-gate effects and dies
at the first idempotency guard, which CLP-13-001 requires to return `FAILURE`
and write nothing — aborting before the gate is ever reached. Option 3 was
rejected because two halves can drift; a single routing tree cannot.

### The rules that follow

**Authority comes from the stored ask, never from the reply.** ADR-0026's trust
rule — roles come from the stored `Offer`, not the received `Accept` — is
generalized: the Proposal is authoritative and the reply is only a yes. An
asker reads what to do from the ask it stored, never from what the answer
claims.

**Every ask carries its own deadline** in `end_time`, which is already present
on every AS2 object and is therefore visible to the answerer.

**Expiry consequence is fixed per ask kind; duration is configurable.** Some
asks remain useful when answered late (admitting a participant); others must
not (adopting a case status). Whether a late reply counts is a protocol rule
fixed in the spec, not a deployment setting — two actors disagreeing about
whether a late answer authorized something is divergence, not preference. The
*duration* is safe to configure per actor precisely because it travels on the
wire, so both parties read the same number from the same object.

**Outstanding asks are recorded, in both directions, durably.** A register
holds asks an actor is waiting on and asks it owes: appended when an ask is
emitted and when one is received, removed when the reply lands. It is
actor-scoped rather than case-scoped, so it works before a case exists. It
generalizes `VultronOfferRecord`.

**The register never authorizes.** Two questions, two sources: *what am I
waiting on, and what do I owe?* is answered by the register; *was this
authorized?* is answered by the case ledger, always. A gate reads the ledger and
never the register, so a corrupted or forged register entry cannot permit an
action. This is the same division as `actor_participant_index` (fast index)
versus the canonical record (authority).

**One register class, two instances.** The create / close-on-named-event /
time-out lifecycle, its reaping, and its enumeration are implemented once. The
durable ask register and the existing in-memory `PendingAssertionStore` are two
instances of it with different durability and different authority: the ask
register is durable and may block; the suppressor is ephemeral, is forgotten on
restart by design, and may never block (CLP-06-002, CLP-06-005). CLP-11-002 is
clarified rather than reversed — do not unify the registers; do share the
lifecycle.

**Expiry is noticed opportunistically, plus a Sentinel seam.** The next entry
into a tree observes an expired ask, and a peer's own retry is frequently the
clock. For prompt reaping, core exposes a general-purpose
`reap-expired-asks` trigger. Per `notes/coordination-agents.md`, a Sentinel
operates exclusively on the call-in surface and has no BT call-out point, so
reaping belongs to an external watcher rather than a loop inside core. The same
endpoint makes expiry testable causally instead of by elapsed time, which
EDF-06-001 requires.

**Asks are visible to the case.** An ask is an ordinary canonical entry and
replicates normally, so an outstanding decision — and a stalled one — is visible
to participants. Consequently an ask MUST NOT carry content that cannot be
disclosed to every case participant; private rationale belongs in a
directly-addressed `Note`. Delivering the fact of an ask while directing its
detail would require redaction with proofs, which the project does not have —
`notes/stub-objects.md` describes redaction as future work — and committing a
stub instead would violate CLP-02-003 and CLP-07-012.

**Failure to process is answered, not left to time out.** An authenticated
sender whose message fails after authentication receives
`Create(ProcessingFault)`. This closes the asker's register entry immediately
rather than costing it a full deadline of silence for a failure that took
milliseconds. It is a dedicated object type rather than a reason field on an
existing reply, because SE-08-003 prefers a dedicated type over field-level
discrimination, and `Create(<minted object>)` is the established idiom
(`Create(CaseProposal)`) — `Reject` presupposes something rejectable, which
unreadable traffic does not provide. Unauthenticated or unparseable traffic is
dropped silently; explaining a parser failure to a stranger is an oracle.

The fault carries a failure class and a pointer, never an echo: in the
protocol-invalid case a typed copy of the failed activity cannot be
constructed, because constructing it is what failed. It is structured as
RFC 9457 Problem Details, with fault types as URIs minted in the Vultron
namespace (VM-10-001, ADR-0069) — so the canonical list is dereferenceable and
extensible without a schema change.

The *unreadable message* never enters the ledger; there is no legible assertion
to record. The *fault statement* does — it is a true, legible statement about a
message that arrived, replicated like any other recorded entry. It is not
per-actor observability content, so CLP-07-004 is unaffected: the fact of a
fault is protocol history, while the diagnosis of why belongs in the actor's own
log.

**A duplicate request after a reply re-sends the stored reply.** Where a request
is repeated because the reply was lost, the answerer re-sends the frozen
original unchanged (VM-08-003), same identity. It reads as the original arriving
late rather than a second decision, which is what CP-05-005's irrevocability
rule requires.

### Consequences

- Good: no framework change is needed; the execution model that appeared to be
  the blocker turns out never to have been on the path
- Good: `RequireCaseOwnerApprovalNode` becomes reachable, so the ADR-0046 /
  ADR-0076 authorization model is implementable for the first time
- Good: the same mechanism serves permission asks, participant admission,
  ownership transfer, and pre-case proposal handshakes — the register is
  actor-scoped, so it does not require a case to exist
- Good: a Case Owner gains an enumerable list of decisions they owe, which is
  the surface a human, a UI, or an agent acts through
- Good: silent indefinite stalls become bounded — by a deadline, by a fault, or
  by a peer's retry
- Neutral: `RequireCaseOwnerApprovalNode` is deleted rather than completed. It
  is replaced by an ask subtree at the front of a routing tree and an
  approval-recorded check ahead of the action
- Neutral: pending decisions become visible to all case participants. This is
  intended, but it constrains what an ask may carry
- Bad: the emit path must be consolidated first. `outbox_append` is called from
  roughly twenty modules and at least four private `_emit` helpers exist, so
  there is no single place in which registration can be made structural
- Bad: expiry is not prompt until a Sentinel is wired; until then an expired ask
  is noticed only when something next enters the tree or the reap trigger is
  called

## Validation

- No node in `vultron/` returns `Status.RUNNING`; a gated tree returns `SUCCESS`
  after emitting its ask, and the emitted ask appears in the actor's outbox
- Re-entering a gated tree after an ask has been emitted produces no second ask
  and no repeated pre-gate effect
- A gate consulted with an `Accept` recorded in the ledger returns `SUCCESS`;
  with a `Reject` recorded it returns `FAILURE`; with neither recorded it emits
  the ask and terminates
- An ask past its deadline under void semantics does not authorize its action
  even when an `Accept` is subsequently recorded
- The ask register is readable across restarts; the suppressor is not
- A gate reads authorization from the ledger; an architecture test confirms no
  gate node reads the ask register

## More Information

- Supersedes the mechanism implied by EDF-04-002 (`RUNNING` while awaiting
  input); replaced by ask-and-terminate
- Amends **ADR-0076**: its capability-shape assignment (Evaluator — "the
  call-out answers a yes/no question") is incorrect for an approval gate,
  because at the moment of asking no answer exists and an Evaluator can
  therefore only ever answer no. The conservative-default requirement it
  establishes is unaffected
- Amends **ADR-0046**: the two gates become routing subtrees rather than
  single-tick evaluator call-outs
- Discharges the deferral recorded in **ADR-0049**, which asked that sender
  notification be *"designed on its own merits"* rather than ported from a
  fuzzer stub. ADR-0049's decision — that core does not model the RE/EE/CE/GE/GI
  message family — is unchanged; one fault object type is not that family
- Generalizes the trust rule of **ADR-0026** from participant roles to every ask
- Sources: CONCERN-2829 (planning group G01), CONCERN-2812, CONCERN-2809,
  CONCERN-2657, CONCERN-1880, CONCERN-2367, CONCERN-2369, IDEA-2796
- Specs: `specs/protocol-asks.yaml`; amendments to CLP-11, EDF-04, RSH-07,
  CP-05, TRIG-04
- Notes: `notes/protocol-asks.md`
