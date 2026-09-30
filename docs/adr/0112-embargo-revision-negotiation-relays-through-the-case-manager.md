---
status: accepted
date: 2026-09-30
deciders: Allen D. Householder
consulted: >-
  Claude Fable 5.1; notes/embargo-lifecycle.md,
  notes/embargo-default-semantics.md, notes/participant-embargo-consent.md,
  notes/case-communication-model.md, specs/em-behavior.yaml EMB-03 through
  EMB-05, specs/embargo-policy.yaml EP-04, EP-05, EP-08,
  specs/participant-case-replica.yaml PCR-08,
  specs/received-status-handling.yaml RSH-08,
  docs/adr/0093-signatory-declined-pec-transition.md,
  docs/adr/0108-one-move-one-mover-case-state-flows-through-the-case-manager-and-the-ledger.md,
  docs/adr/0109-a-container-emits-only-as-actors-it-hosts.md,
  Concerns #3892, #3836, #3863
informed: CERT/CC Vultron protocol team
stakeholder_type: [project-contributor]
---

# Embargo Revision Negotiation Relays Through the CASE_MANAGER; the Ledger Carries State but Never Asks

## Context and Problem Statement

An embargo revision is proposed while an embargo is active.
The protocol behaviour spec says a Participant in EM `ACTIVE` that receives the revision (EV) moves to EM `REVISE` and acknowledges it (EMB-03-001), a Participant already in `REVISE` acknowledges a counter-revision without a further transition (EMB-03-002), and one whose case is already public, exploited or attacked terminates instead (EMB-03-003).
Three concerns found that this half of the embargo lifecycle exists in one store only:

- **#3892.** No received path moves any EM state on an inbound `Invite(EmbargoEvent)`.
  The received Invite tree stores the activity, moves the *invitee's* consent to `INVITED`, records the proposal index and commits a ledger entry.
  The proposer's own trigger moved its local case to `REVISE`; nobody else's case moved, so everything keyed on `EM.REVISE` ran in the proposer's container alone.
  There were no EMB-03 marker tests.
- **#3863.** Shortest-wins at case creation (EP-04-003) registers the longer of the two proposals as a pending revision through `EmbargoLifecycle.propose_embargo`, in the CASE_MANAGER's store only.
  No Invite is emitted for it, and the registration never reaches `pending_embargo_proposal_index`, so the owner cannot even accept it through the default earliest-expiring selection (EP-08-002).
- **#3836.** Termination prunes the terminated embargo's own entry from both open-proposal records and leaves every open revision of it in place, where the next default selection can pick a revision of an embargo that no longer exists (EP-08-003).

Underneath all three is one question the specs answer but the embargo trees never adopted: **how does a revision proposal become visible to every replica, and what does a participant do about it?**
The interview that produced this decision also surfaced a confusion worth naming.
The behavioural specs are written in the voice of the formal protocol, in which every Participant is a peer and every Participant "receives EV".
In the CASE_MANAGER topology this project runs (PCR-08-001, ADR-0108) a participant addresses its proposal to the CASE_MANAGER alone, so "the Participant receiving EV" is the CASE_MANAGER, and every other participant learns the outcome from the ledger.
Building parse-and-respond handling for a non-manager receiving a peer's proposal is building code for a message that should not arrive.

## Decision Drivers

- Only the CASE_MANAGER turns an announcement into case state, and every other participant takes case state from the ledger (ADR-0108, PCR-03-001, RSH-08-003).
  Every event type the CASE_MANAGER commits needs a replica apply node, and replay must exist before the direct-receipt shortcut is gated (RSH-08-004).
- A container emits only as actors it hosts; a participant that wants the CASE_MANAGER to act sends it the participant's own activity, and the CASE_MANAGER's received tree performs the delegated emit and commits it in that tree (ADR-0109, CM-24-004).
- The case Invite already runs as a relay: the owner asks the CASE_MANAGER, the CASE_MANAGER invites as sender with the owner attributed, and the invitee answers the CASE_MANAGER (PCR-08-007 through PCR-08-009).
  An embargo revision has the same shape and should not invent a second one.
- Consent is per embargo and lapse fires at activation (ADR-0093 as revised for #3884, EP-05).
  Proposing terms records consent to them; a revision proposal changes nobody's consent state; the owner's activation of longer terms is where signatories who have not accepted lapse.
- The protocol already has participants SHOULD follow consensus on embargo terms (VP-08-003) and deliberately leaves "quorum" undefined so communities can adopt their own decision rules (VP-08-012).
  Any rule about how long the owner waits must leave that room.
- A case has one active embargo (VP-04-002), so every proposal open while EM is `ACTIVE` or `REVISE` is a revision of the active embargo.
  No field linking a revision to the embargo it revises is needed to know which proposals a termination decides.

## Considered Options

1. **Write `REVISE` at every inbox.** The received Invite tree calls `propose_embargo(OBSERVED)` wherever it runs, matching what the received Accept and teardown trees do today.
2. **Ledger only.** The CASE_MANAGER commits the proposal; replicas reconstruct `REVISE` from the entry; a participant that sees the proposal in the ledger answers it from there.
   No Invite is sent to anyone.
3. **Relay through the CASE_MANAGER and record everything; the ledger carries state and never asks.** The CASE_MANAGER adjudicates the proposal, moves the canonical case, commits, then invites the participants and commits each Invite; participants answer the Invite addressed to them; the CASE_MANAGER commits the answers; the owner's answer also decides the embargo; replicas reconstruct every step from the ledger.

## Decision Outcome

Chosen option: **relay through the CASE_MANAGER and record everything (option 3)**.

The rule in one sentence: *ledger entries carry case state to replicas and set no parse-and-respond expectation; the protocol interactions the specs already define still happen, relayed through the CASE_MANAGER, and each of them is recorded.*
The ledger augments the negotiation as the record of the case.
It does not replace it.

### The flow

1. **A participant proposes a revision by sending its `Invite(EmbargoEvent)` to the CASE_MANAGER only** (PCR-08-001).
   A participant that receives a peer's proposal directly stores it and writes nothing (RSH-08-003); that delivery is a misrouting, not a protocol case.
2. **The CASE_MANAGER adjudicates the proposal and moves the canonical case.**
   With the case still embargo-eligible it moves EM `ACTIVE → REVISE` through `EmbargoLifecycle`, or stays at `REVISE` for a counter-revision, and commits the proposal entry.
   This is where EMB-03-001 and EMB-03-002 are realised: "the Participant receiving EV" is the CASE_MANAGER on receipt, and every other participant through replay.
   With the case public, exploited or attacked it refuses the proposal, as the received tree already does (EMB-03-003).
   The fan-out of this entry tells every replica the case is under revision.
   That is all it tells them.
3. **The CASE_MANAGER then emits a revision Invite to every participant except the proposer**, as the ActivityStreams `actor`, with the proposer in `attributedTo` (CM-24-001, CM-24-002), and commits each emission.
   The proposer is excluded because proposing terms is consenting to them (ADR-0093), so an Invite to the proposer asks a question already answered, and because the response decision has a call-out where a human or agent may decline, which for the proposer would produce a state the protocol has no name for: a proposer that has withdrawn from its own open proposal.
   Excluding the proposer costs one filter; the proposer's identity is on the activity just adjudicated.
4. **A participant answers the Invite addressed to it**, through its existing response decision (EMB-15), with `Accept` or `Reject` sent to the CASE_MANAGER.
   On receipt of an Invite it writes no case state and no consent state; consent moves when the CASE_MANAGER commits the answer, and the replica learns it from the ledger.
   A revision Invite to a participant already `SIGNATORY` to the active embargo changes its consent state not at all: the PEC `INVITE` trigger is legal only from `UNBOUND`, `LAPSED` or `DECLINED` (CM-18-003), and under EP-05-002 a proposal changes no consent.
   The current receive tree applies `INVITE` unconditionally and would fault on a signatory; it is corrected.
5. **The owner's answer is a consent record and also the decision.**
   `Accept` activates the revision (`REVISE → ACTIVE` under the new terms, with the EP-05-001 consent re-evaluation); `Reject` keeps the prior terms (`REVISE → ACTIVE` under the old ones).
   Both are committed and replicated.
   The owner MAY decide at any time without waiting for other participants' answers.
   The owner SHOULD wait for at least some answers, to gauge consensus (VP-08-003).
   The protocol defines no quorum and no vote; which answers, how many, and how long are actor policy, a natural call-out point rather than a rule (VP-08-012).
6. **The Invites earn their place under owner fiat, and the reason is recorded so the question stops recurring.**
   They are not a vote.
   They gather the consent records the activation cascade reads: when the owner activates longer terms, every signatory who accepted them stays bound and every signatory who did not lapses (EP-05-001).
   The owner's decision settles the embargo; the answers settle who is bound by it.
7. **Replicas reconstruct every step from the ledger.**
   The proposal entry, each Invite emission, each consent answer and the owner's decision each have a replica apply node reachable from the announce tree (RSH-08-004), driving EM through `EmbargoLifecycle` in `OBSERVED` mode as the teardown apply node already does.
   With every event type of this flow covered, the participant-side embargo trees become gateable under the ledger-replay task without further work.
8. **The creation-time revision follows the same relay.**
   The loser of shortest-wins (EP-04-003) is proposed by the CASE_MANAGER on behalf of whichever party's terms lost, attributed to that party, committed as a proposal entry, indexed in the open-proposal record so the owner's default selection can reach it, and relayed as an Invite to the other party.
   The party whose terms lost is the proposer and is not invited.
9. **Termination decides every open proposal.**
   Because a case has one active embargo, every proposal open while EM is `ACTIVE` or `REVISE` is a revision of it, and a revision of an embargo that no longer exists cannot be accepted.
   `terminate_active_embargo` clears both open-proposal records, and because the teardown apply node runs the same method in `OBSERVED` mode the rule holds on every replica with no extra work.
10. **The emit-side shortcut is noted and left alone.**
    A proposer's trigger still moves its own local EM to `REVISE` before the CASE_MANAGER has answered.
    That is the emit-side optimism ADR-0108 explicitly left unchanged; it is recorded here so nobody reads the local write as the mechanism by which the case moved.

### Consequences

- Good, because EMB-03 through EMB-05 stop describing behaviour that runs in one store: the CASE_MANAGER's canonical case reflects that a revision is under negotiation, and every replica reconstructs it.
- Good, because the embargo revision reuses the case-Invite relay and the delegated-authorship contract instead of adding a message type or a second routing shape.
- Good, because the "why ask if the owner decides anyway" question has a written answer that follows from the consent model, not from a voting rule the protocol declines to have.
- Good, because the owner's latitude is stated in the protocol's own register (MAY act, SHOULD gauge consensus, no quorum) and leaves actor policy where VP-08-012 puts it.
- Good, because the termination rule needs no schema change.
- Bad, because the CASE_MANAGER emits and commits one Invite per participant per revision, which is more ledger traffic than a single proposal entry.
  This is the price of the protocol interaction being a real one rather than an inference from the ledger.
- Bad, because the received Invite tree, which today runs the same effects at every inbox, has to be split into the CASE_MANAGER's adjudication and a participant's store-and-answer path, and the replay nodes must land before the gating does (RSH-08-004).
- Neutral, because the proposer's local `REVISE` write on the trigger side survives; it is now documented as optimism rather than mistaken for the mechanism.

## Validation

- Unit tests under `test/core/services/embargo_lifecycle/` assert that termination with a revision pending leaves both open-proposal records empty (EP-08-004).
- Tests of the received Invite path assert that the CASE_MANAGER moves the canonical case to `REVISE` and queues an Invite for each non-proposer participant, and that a non-manager receiving an Invite directly writes no case or consent state (EP-09-001 through EP-09-003).
- A test asserts a signatory that receives a revision Invite stays `SIGNATORY` and the tree succeeds (EP-09-004).
- A test asserts the owner's `Accept` from `REVISE` activates the revision with no other participant having answered (EP-09-005).
- Tests of `RegisterLongerProposalAsRevisionNode` assert the creation-time revision is indexed and an Invite is queued for the party whose terms won (EP-04-011).
- The RSH-08-004 ratchet covers the proposal, Invite, consent and decision event types once their replay nodes land.
- Until the implementation issues land, the new `kind: protocol` requirements are carried by strict `xfail` marker tests naming the tracking issue.

## Pros and Cons of the Options

### Write `REVISE` at every inbox

- Good, because it is the smallest change and matches the received Accept and teardown trees as they stand today.
- Bad, because it is exactly the any-sender shortcut ADR-0108 and the ledger-replay task plan to gate off, so it would be built to be removed.
- Bad, because it presumes a non-manager receives a peer's proposal directly, which PCR-08-001 forbids.

### Ledger only

- Good, because it needs no Invite emission and no per-participant commits.
- Bad, because it turns a ledger entry into a request: a participant would have to parse the proposal out of the entry and answer it.
  The ledger is a channel for case state, not a protocol interaction, and giving it parse-and-respond semantics would let every future entry type become an implicit request.
- Bad, because it abandons the EP/EV/EC/EJ negotiation the behavioural specs define, so the formal model and the implementation would describe different protocols.

### Relay through the CASE_MANAGER and record everything (chosen)

- Good, because it is what PCR-08, CM-24 and RSH-08 already say, applied to embargoes.
- Good, because the protocol interactions stay real and the ledger stays a record of them.
- Bad, because it is the most emissions and the most replay nodes of the three.

## More Information

Source: Concerns #3892, #3836 and #3863, planned as one bundle under epic #3408 (embargo negotiation, defaults and lifecycle).
The shared design idea is that a revision proposal must be visible to every replica while it is open and retired everywhere when the embargo it revises ends.

Related decisions: ADR-0093 (consent is per embargo; lapse fires at activation), ADR-0100 (no multi-candidate embargo poll), ADR-0108 (one move, one mover), ADR-0109 (a container emits only as actors it hosts).

Generated spec requirements: `embargo-policy.yaml` EP-09-001 through EP-09-007, EP-04-011, EP-08-004; `em-behavior.yaml` EMB-03 group description.
