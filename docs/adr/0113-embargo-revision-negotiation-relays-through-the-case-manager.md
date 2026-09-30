---
status: accepted
date: 2026-09-30
deciders: Allen D. Householder
consulted: >-
  Claude Fable 5.1; notes/embargo-lifecycle.md,
  notes/embargo-default-semantics.md, notes/participant-embargo-consent.md,
  notes/case-communication-model.md, notes/protocol-asks.md,
  specs/em-behavior.yaml EMB-01 through EMB-06,
  specs/embargo-policy.yaml EP-04, EP-05, EP-07, EP-08,
  specs/case-management.yaml CM-24, CM-28,
  specs/participant-case-replica.yaml PCR-08,
  specs/received-status-handling.yaml RSH-08,
  specs/protocol-asks.yaml ASK-01 through ASK-08,
  specs/multi-actor-demo.yaml DEMOMA-20, DEMOMA-21,
  docs/adr/0080-protocol-asks-not-suspended-behaviors.md,
  docs/adr/0093-signatory-declined-pec-transition.md,
  docs/adr/0108-one-move-one-mover-case-state-flows-through-the-case-manager-and-the-ledger.md,
  docs/adr/0109-a-container-emits-only-as-actors-it-hosts.md,
  Concerns #3892, #3836, #3863, #3918
informed: CERT/CC Vultron protocol team
stakeholder_type: [project-contributor]
---

# Embargo Negotiation Relays Through the CASE_MANAGER; the Ledger Carries State but Never Asks

## Context and Problem Statement

An embargo is proposed for a case, or a revision is proposed while an embargo is active.
The protocol behaviour specs say a Participant that receives the proposal (EP) moves to EM `PROPOSED` and acknowledges it (EMB-01-001), a Participant in `ACTIVE` that receives the revision (EV) moves to `REVISE` and acknowledges it (EMB-03-001), a Participant already in `PROPOSED` or `REVISE` acknowledges a counter-proposal without a further transition (EMB-01-003, EMB-03-002), and one whose case is already public, exploited or attacked rejects or terminates instead (EMB-01-002, EMB-03-003).
Three concerns found that the revision half of this lifecycle existed in one store only, and a fourth found the same shape everywhere else the rule reaches:

- **#3892.** No received path moved any EM state on an inbound `Invite(EmbargoEvent)`.
  The received Invite tree stored the activity, moved the *invitee's* consent to `INVITED`, recorded the proposal index and committed a ledger entry.
  The proposer's own trigger moved its local case to `REVISE`; nobody else's case moved, so everything keyed on `EM.REVISE` ran in the proposer's container alone.
  There were no EMB-03 marker tests.
- **#3863.** Shortest-wins at case creation (EP-04-003) registered the longer of the two proposals as a pending revision through `EmbargoLifecycle.propose_embargo`, in the CASE_MANAGER's store only.
  No Invite was emitted for it, and the registration never reached `pending_embargo_proposal_index`, so the owner could not even accept it through the default earliest-expiring selection (EP-08-002).
- **#3836.** Termination pruned the terminated embargo's own entry from both open-proposal records and left every open revision of it in place, where the next default selection could pick a revision of an embargo that no longer exists (EP-08-003).
- **#3918.** The first proposal for a case (EM `NONE → PROPOSED`) had the identical defect: addressed to the CASE_MANAGER alone, moved no EM state on receipt, so `PROPOSED` existed only in the proposer's store.
  Every embargo trigger (propose, revise, accept, reject, terminate) wrote its own local EM state before the CASE_MANAGER answered, then declared that state to the manager, and nothing corrected the write when the manager refused.
  Every store that received an Invite derived its own RSVP deadline from its own configuration, because no trigger put one on the wire; lapse was evaluated only when a late `Accept` arrived, and the lapse entry was committed in whichever store that happened to be.
  No EK acknowledgement existed anywhere in the production stack.
  A "no CASE_MANAGER, send directly" fallback survived in spec CM-24-003 and in two nodes, though no creation path can produce a case without a manager.

Underneath all of them is one question the specs answer but the embargo trees never adopted: **how does a proposal become visible to every replica, and what does a participant do about it?**
The interviews that produced this decision also surfaced a confusion worth naming.
The behavioural specs are written in the voice of the formal protocol, in which every Participant is a peer and every Participant "receives EP" or "receives EV".
In the CASE_MANAGER topology this project runs (PCR-08-001, ADR-0108) a participant addresses its proposal to the CASE_MANAGER alone, so "the Participant receiving EP/EV" is the CASE_MANAGER, and every other participant learns the outcome from the ledger.
Building parse-and-respond handling for a non-manager receiving a peer's proposal is building code for a message that should not arrive.

## Decision Drivers

- Only the CASE_MANAGER turns an announcement into case state, and every other participant takes case state from the ledger (ADR-0108, PCR-03-001, RSH-08-003).
  Every event type the CASE_MANAGER commits needs a replica apply node, and replay must exist before the direct-receipt shortcut is gated (RSH-08-004).
- A container emits only as actors it hosts; a participant that wants the CASE_MANAGER to act sends it the participant's own activity, and the CASE_MANAGER's received tree performs the delegated emit and commits it in that tree (ADR-0109, CM-24-004).
- The case Invite already runs as a relay: the owner asks the CASE_MANAGER, the CASE_MANAGER invites as sender with the owner attributed, and the invitee answers the CASE_MANAGER (PCR-08-007 through PCR-08-009).
  An embargo proposal has the same shape and should not invent a second one.
- An ask is an addressed activity that terminates the asker's behaviour, carries its own deadline in `endTime`, is recorded by its emitter, and is authorised by the ledger and never by the reply (ADR-0080, ASK-01, ASK-03-004, ASK-04-001).
  The ephemeral half of that bookkeeping already exists as the pending-assertion store (SYNC-11, CLP-06), used by the note trigger.
- The CASE_MANAGER is the enforcement authority for embargo invite expiry (CM-28-003), and an explicit `Invite.end_time` is authoritative over any receiver-local window (CM-28-002).
- Consent is per embargo and lapse fires at activation (ADR-0093 as revised for #3884, EP-05).
  Proposing terms records consent to them; a proposal changes nobody's consent state; the owner's activation of longer terms is where signatories who have not accepted lapse.
- The protocol already has participants SHOULD follow consensus on embargo terms (VP-08-003) and deliberately leaves "quorum" undefined so communities can adopt their own decision rules (VP-09-007).
  Any rule about how long the owner waits must leave that room.
- A case has one active embargo (VP-04-002), so every proposal open while EM is `ACTIVE` or `REVISE` is a revision of the active embargo.
  No field linking a revision to the embargo it revises is needed to know which proposals a termination decides.
- A case has a `CASE_MANAGER` holder from creation onward: the CaseActor registers itself as `COORDINATOR` + `CASE_MANAGER` (ADR-0041), or the creating actor registers itself as `CASE_OWNER` + `CASE_MANAGER` (CM-02-015), and delegation hands the role on.
  The role is never unfilled, so no arm of any tree needs to handle its absence.

## Considered Options

1. **Write EM state at every inbox.** The received Invite tree calls `propose_embargo(OBSERVED)` wherever it runs, matching what the received Accept and teardown trees did.
2. **Ledger only.** The CASE_MANAGER commits the proposal; replicas reconstruct the state from the entry; a participant that sees the proposal in the ledger answers it from there.
   No Invite is sent to anyone.
3. **Relay through the CASE_MANAGER and record everything; the ledger carries state and never asks.** The CASE_MANAGER adjudicates the proposal, moves the canonical case, commits, then invites the participants and commits each Invite; participants answer the Invite addressed to them; the CASE_MANAGER commits the answers; the owner's answer also decides the embargo; replicas reconstruct every step from the ledger.

## Decision Outcome

Chosen option: **relay through the CASE_MANAGER and record everything (option 3)**, for every embargo proposal, first or revision.

The rule in one sentence: *ledger entries carry case state to replicas and set no parse-and-respond expectation; the protocol interactions the specs already define still happen, relayed through the CASE_MANAGER, and each of them is recorded.*
The ledger augments the negotiation as the record of the case.
It does not replace it.

### The flow

1. **A participant proposes an embargo, or a revision, by sending its `Invite(EmbargoEvent)` to the CASE_MANAGER only** (PCR-08-001).
   A participant that receives a peer's proposal directly stores it and writes nothing (RSH-08-003); that delivery is a misrouting, not a protocol case.
   The published-default path (EP-04-001) emits no proposal, so nothing is relayed for it.
2. **The CASE_MANAGER adjudicates the proposal and moves the canonical case.**
   With the case still embargo-eligible it moves EM `NONE → PROPOSED` for a first proposal or `ACTIVE → REVISE` for a revision through `EmbargoLifecycle`, which already derives the destination from the prior state, or stays put for a counter-proposal, and commits the proposal entry.
   This is where EMB-01-001, EMB-01-003, EMB-03-001 and EMB-03-002 are realised: "the Participant receiving EP/EV" is the CASE_MANAGER on receipt, and every other participant through replay.
   With the case public, exploited or attacked it refuses the proposal, as the received tree already does (EMB-01-002, EMB-03-003), and its `Reject` back to the proposer closes the proposer's pending entry (step 10).
   The fan-out of this entry tells every replica the case is under proposal or revision.
   That is all it tells them.
3. **The CASE_MANAGER then emits an Invite to every participant except the proposer**, as the ActivityStreams `actor`, with the proposer in `attributedTo` (CM-24-001, CM-24-002), and commits each emission.
   Each relayed Invite carries `end_time` equal to its own `published` time plus the configured RSVP window, within the EP-07 floor and ceiling; the Invites of one round go out in sequence and need not share an instant (CM-28-012).
   At the commit of each emission the CASE_MANAGER records the deadline on the invitee's record and applies the PEC `INVITE` trigger where legal; the replica apply node does the same (CM-28-013).
   The proposer is excluded because proposing terms is consenting to them (ADR-0093), so an Invite to the proposer asks a question already answered, and because the response decision has a call-out where a human or agent may decline, which for the proposer would produce a state the protocol has no name for: a proposer that has withdrawn from its own open proposal.
   Excluding the proposer costs one filter; the proposer's identity is on the activity just adjudicated.
4. **A participant answers the Invite addressed to it**, through its existing response decision (EMB-15), with `Accept` or `Reject` sent to the CASE_MANAGER.
   On receipt of an Invite it writes no case state, no consent state and no deadline; consent moves when the CASE_MANAGER commits the answer, and the replica learns it from the ledger.
   The invitee is the Invite's sole `to` recipient; an Invite with no recipient or several is refused as a misrouting, never guessed at from the receiving actor (EP-09-010).
   A revision Invite to a participant already `SIGNATORY` to the active embargo changes its consent state not at all: the PEC `INVITE` trigger is legal only from `UNBOUND`, `LAPSED` or `DECLINED` (CM-18-003), and under EP-05-002 a proposal changes no consent.
   The receive tree that applied `INVITE` unconditionally and would fault on a signatory is corrected.
5. **The owner's answer is a consent record and also the decision.**
   `Accept` activates the embargo (`PROPOSED → ACTIVE`, or `REVISE → ACTIVE` under the new terms with the EP-05-001 consent re-evaluation); `Reject` clears a first proposal (`PROPOSED → NONE`) or keeps the prior terms (`REVISE → ACTIVE` under the old ones).
   Both are committed and replicated.
   The owner MAY decide at any time without waiting for other participants' answers.
   The owner SHOULD wait for at least some answers, to gauge consensus (VP-08-003).
   The protocol defines no quorum and no vote; which answers, how many, and how long are actor policy, a natural call-out point rather than a rule (VP-09-007).
6. **The Invites earn their place under owner fiat, and the reason is recorded so the question stops recurring.**
   They are not a vote.
   They gather the consent records the activation cascade reads: when the owner activates longer terms, every signatory who accepted them stays bound and every signatory who did not lapses (EP-05-001).
   The owner's decision settles the embargo; the answers settle who is bound by it.
7. **Only the CASE_MANAGER evaluates lapse, and a lapse is a replicated entry.**
   The RSVP deadline the manager stamped in step 3 is the only one anybody holds.
   Lapse stays lazy (CM-28-007), but it is derived by the manager alone; the lapsed-invitation entry (CM-28-009) is committed behind the manager's role gate and has a replay node like every other event type, so a replica learns a lapse and never computes one (CM-28-014).
8. **Replicas reconstruct every step from the ledger.**
   The proposal entry, each Invite emission, each consent answer, each lapse and the owner's decision each have a replica apply node reachable from the announce tree (RSH-08-004), driving EM and PEC through `EmbargoLifecycle` in `OBSERVED` mode as the teardown apply node already does.
   With every event type of this flow covered, the participant-side embargo trees become gateable under the ledger-replay task without further work.
9. **The creation-time revision follows the same relay.**
   The loser of shortest-wins (EP-04-003) is proposed by the CASE_MANAGER on behalf of whichever party's terms lost, attributed to that party, committed as a proposal entry, indexed in the open-proposal record so the owner's default selection can reach it, and relayed as an Invite to the other party.
   The party whose terms lost is the proposer and is not invited.
10. **A trigger writes shared EM state only as the CASE_MANAGER; otherwise it asks and records the ask.**
    Every embargo trigger wrote its local EM state before the manager had answered, and nothing corrected it when the manager refused.
    Now a trigger writes EM state only when its actor holds `CVDRole.CASE_MANAGER` for the case, under the same role gate every received tree uses; otherwise it emits the activity to the manager, records it in the pending-assertion store exactly as the note trigger does, writes nothing, and declares nothing, and its replica moves when the manager's commit is announced (EP-09-008).
    The manager's `Reject` of a refused proposal closes the pending entry.
    The case-status declaration each trigger sent after its local write goes with it, for EM.
    A participant's own RM and status claims are its own to assert (RSH-06-001) and keep their local write.
    An owner that still holds the manager role after creation writes canonically until it delegates; the gate needs no special case because the role is never unfilled (CM-24-006).
    ADR-0108 carries the matching amendment withdrawing the emit-side latitude it had left in place.
11. **Termination decides every open proposal.**
    Because a case has one active embargo, every proposal open while EM is `ACTIVE` or `REVISE` is a revision of it, and a revision of an embargo that no longer exists cannot be accepted.
    `terminate_active_embargo` clears both open-proposal records, and because the teardown apply node runs the same method in `OBSERVED` mode the rule holds on every replica with no extra work.
12. **The ledger commit is the acknowledgement.**
    The behavioural specs have every receiver "emit EK".
    No EK exists in the production stack — no `MessageSemantics` member, pattern, factory or node — and MSM-02-009 records that its purpose is served by ledger hash-chain continuity.
    The CASE_MANAGER's commit of a received embargo activity, fanned out as `Announce(CaseLedgerEntry)`, is the acknowledgement; no EK message is built (EP-09-009).
13. **The embargo Invite is an ask kind, and a relayed ask is the manager's.**
    `Invite(EmbargoEvent)` fits ADR-0080's model exactly: closed by `Accept` or `Reject` from the invitee, deadline in `endTime`, and a reply after the deadline still honoured (EMB-17) — the stale, not void, expiry consequence (ASK-03-007).
    The manager records the relayed Invites as its own outstanding asks; the proposer holds only its own proposal (ASK-04-010).
    Counter-proposals need no further rule: a counter is a fresh proposal, the manager never counters on its own and never invites the proposer, so the relay adds no loop, and several open proposals resolve in EP-08 order.
14. **The CASE_MANAGER role is never unfilled, and no code carries an arm for its absence.**
    CM-24-003, which codified a "no dedicated CASE_MANAGER, send directly" fallback, is superseded by CM-24-006; the delegated-context helper's fallback branch and the two nodes that succeeded with a warning when the resolver found nobody are retired with it.
    A resolver that finds no holder fails, because that can only mean a corrupt roster.

### Consequences

- Good, because EMB-01 through EMB-06 stop describing behaviour that runs in one store: the CASE_MANAGER's canonical case reflects that an embargo is under proposal or revision, and every replica reconstructs it.
- Good, because the embargo proposal reuses the case-Invite relay, the delegated-authorship contract and the ask model instead of adding a message type, a second routing shape or a second register.
- Good, because a proposer's replica can never disagree with the canonical case: there is no optimistic write to correct, so the refusal path needs no rollback.
- Good, because every replica reads the same RSVP deadline off the same Invite, and lapse has one evaluator.
- Good, because the "why ask if the owner decides anyway" question has a written answer that follows from the consent model, not from a voting rule the protocol declines to have.
- Good, because the owner's latitude is stated in the protocol's own register (MAY act, SHOULD gauge consensus, no quorum) and leaves actor policy where VP-09-007 puts it.
- Good, because the termination rule needs no schema change.
- Bad, because the CASE_MANAGER emits and commits one Invite per participant per proposal, which is more ledger traffic than a single proposal entry.
  This is the price of the protocol interaction being a real one rather than an inference from the ledger.
- Bad, because the received Invite tree, which ran the same effects at every inbox, has to be split into the CASE_MANAGER's adjudication and a participant's store-and-answer path, and the replay nodes must land before the gating does (RSH-08-004), on the received side and on the trigger side alike.
- Bad, because five trigger trees change shape and the trigger-activity port learns to carry `end_time` and `attributed_to`.
- Neutral, because a demo can no longer read a result off the triggering actor's replica immediately after a trigger; it polls the canonical case or waits for the fan-out, which is what the demo specs now say (DEMOMA-20, DEMOMA-21).

## Validation

- Unit tests under `test/core/services/embargo_lifecycle/` assert that termination with a revision pending leaves both open-proposal records empty (EP-08-004).
- Tests of the received Invite path assert that the CASE_MANAGER moves the canonical case to `PROPOSED` from `NONE` and to `REVISE` from `ACTIVE`, queues an Invite for each non-proposer participant carrying `end_time` = `published` + window, and that a non-manager receiving an Invite directly writes no case, consent or deadline state (EP-09-001 through EP-09-003, CM-28-012, CM-28-013).
- A test asserts a signatory that receives a revision Invite stays `SIGNATORY` and the tree succeeds (EP-09-004).
- A test asserts the owner's `Accept` from `REVISE` activates the revision with no other participant having answered (EP-09-005).
- Tests of `propose_embargo_trigger_bt` assert a non-manager writes no EM state, queues the Invite to the manager, records a pending assertion and queues no `Add(CaseStatus)`, while the role holder writes `PROPOSED` (EP-09-008).
- A test asserts no embargo-acknowledgement semantic or pattern exists (EP-09-009); tests deliver an Invite with two recipients and with none and assert refusal (EP-09-010).
- A test runs the late-`Accept` path as a non-manager and asserts no lapse entry is committed; a test replays a lapse entry into a replica (CM-28-014).
- Tests of both creation trees assert a `CASE_MANAGER` holder exists after creation, and tests of the close-case emit and teardown announce assert FAILURE when none is found (CM-24-006).
- A marker test of `RegisterLongerProposalAsRevisionNode` asserts the creation-time revision is indexed; the implementation's tests assert an Invite is queued for the party whose terms won (EP-04-011).
- The RSH-08-004 ratchet covers the proposal, Invite, consent, lapse and decision event types once their replay nodes land.
- Until the implementation issues land, the `kind: protocol` requirements this decision generates are carried by strict `xfail` marker tests naming the tracking issue.

## Pros and Cons of the Options

### Write EM state at every inbox

- Good, because it is the smallest change and matches the received Accept and teardown trees as they stood.
- Bad, because it is exactly the any-sender shortcut ADR-0108 and the ledger-replay task plan to gate off, so it would be built to be removed.
- Bad, because it presumes a non-manager receives a peer's proposal directly, which PCR-08-001 forbids.

### Ledger only

- Good, because it needs no Invite emission and no per-participant commits.
- Bad, because it turns a ledger entry into a request: a participant would have to parse the proposal out of the entry and answer it.
  The ledger is a channel for case state, not a protocol interaction, and giving it parse-and-respond semantics would let every future entry type become an implicit request.
- Bad, because it abandons the EP/EV/EC/EJ negotiation the behavioural specs define, so the formal model and the implementation would describe different protocols.

### Relay through the CASE_MANAGER and record everything (chosen)

- Good, because it is what PCR-08, CM-24, CM-28, RSH-08 and ADR-0080 already say, applied to embargoes.
- Good, because the protocol interactions stay real and the ledger stays a record of them.
- Bad, because it is the most emissions and the most replay nodes of the three.

## More Information

Source: Concerns #3892, #3836 and #3863, planned as one bundle under epic #3408 (embargo negotiation, defaults and lifecycle); generalised from revisions to every proposal, and extended to the RSVP deadline, the acknowledgement, the ask model, the trigger-side write and the no-manager arm, by Concern #3918's audit of where the rule reaches.
The shared design idea is that a proposal must be visible to every replica while it is open and retired everywhere when the embargo it concerns ends.

Rewritten in place on 2026-09-30 for Concern #3918, as a same-day ADR is (`notes/specs-vs-adrs.md`): the original decided the revision case only, and details 7 and 10 through 14 are new.
Spec and notes references to "ADR-0113 as amended" mean this rewrite; the file name keeps the original slug so inbound links resolve.

Implementation: #3913 (the CASE_MANAGER adjudicates and relays, first proposal and revision alike), #3915 (participant side and replay), #3914 (termination clears every open proposal), #3916 (the creation-time revision), #3814 (replay-then-gate, with the lapse event type in its inventory), #2884 (the embargo Invite as an ask kind), plus the Tasks the #3918 planning PR opened for the RSVP deadline, the trigger-side write gate, the invitee resolution and the CM-24-003 retirement.

Ordering: `propose_embargo` still lapses every signatory on `ACTIVE → REVISE` until #3891 lands, so #3913 depends on #3891; otherwise the first relayed revision would lapse the whole case.
The trigger-side write gate depends on #3915's replay nodes for the same reason RSH-08-004 orders the received side: gate the local write before the replica can move and the proposer's case never leaves `NONE`.

Related decisions: ADR-0080 (an ask is a message, not a suspended behaviour), ADR-0093 (consent is per embargo; lapse fires at activation), ADR-0100 (no multi-candidate embargo poll), ADR-0108 (one move, one mover; amended here to withdraw the emit-side latitude for shared EM state), ADR-0109 (a container emits only as actors it hosts).

Generated spec requirements: `embargo-policy.yaml` EP-09-001 through EP-09-010, EP-04-011, EP-08-004; `case-management.yaml` CM-28-012 through CM-28-014, CM-24-006; `protocol-asks.yaml` ASK-03-007, ASK-04-010; `em-behavior.yaml` EMB-01 and EMB-03 group descriptions; `multi-actor-demo.yaml` DEMOMA-20-002, -006, -007, -011, DEMOMA-21-002, -007, -008, -010.
