---
status: accepted-provisional
date: 2026-11-06
created: 2026-11-06
updated: 2026-11-06
revision: 2
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; Concern #5648, Bug #5641, Concern #6041; ADR-0122, ADR-0152;
  specs/message-semantics-mapping.yaml MSM-07; specs/vultron-as2-mapping.yaml VAM-05
informed: []
stakeholder_type: [project-contributor]
partially_supersedes:
  - 0122-per-embargo-participant-consent.md
---

# The Case Owner Adds an Embargo to the Case, and Each Owner Decision Points at the Proposal It Answers

## Context and Problem Statement

[ADR-0122](0122-per-embargo-participant-consent.md) gave the case owner's decisions on a proposed embargo their own activities, so that `Accept` and `Reject` of an `Invite(EmbargoEvent)` always mean the sender's own consent.
It chose `Accept(EmbargoEvent, target=VulnerabilityCase)` to activate a proposal and `Reject(EmbargoEvent, target=VulnerabilityCase)` to reject one.
Ending an embargo in force is `Remove(EmbargoEvent, origin=VulnerabilityCase)`.

Two problems remain (Concern #5648):

1. Activation is a change to the case: the case gains an embargo.
   It is written as an answer, `Accept`, and only the shape of its object tells it apart from a participant's consent, `Accept(Invite(EmbargoEvent))`.
   A receiver then depends on strict object matching to tell a case change from a consent.
2. Neither decision names the proposal it decides.
   Both carry the `EmbargoEvent`, not the `Invite(EmbargoEvent)` that proposed it, so a reader cannot link the decision to its proposal (Bug #5641).

3. Nothing says how the owner's own answer to a proposal constrains its decision for the case (Concern #6041).
   ADR-0122 lets an owner that declined a proposal activate it anyway, the activation moving its row to `AGREED`, so one activity both decides the case and changes the owner's answer.

The question: **what does the case owner send when it decides a proposed embargo, so that each activity has one meaning and names what it answers, and which of its own answers is consistent with each decision?**

## Decision Drivers

- Each shape means one thing, whoever sends it, so no handler reads the sender to learn what a message means (ADR-0122).
- The verb says what happened: a change to the case reads as a change to the case, an answer as an answer.
- Every response names the activity it answers in `inReplyTo` (RF-08-001).
- The owner's decision for the case never rewrites an answer the owner gave as a participant.
- Before 1.0 the protocol keeps one version only, so a replaced shape is removed, not kept beside its successor.

## Considered Options

- Keep `Accept`/`Reject(EmbargoEvent, target=VulnerabilityCase)` and add `inReplyTo` only.
- The owner adds, rejects and removes the embargo; each decision names the proposal it answers.
- The owner adds the embargo, and rejects a proposal by rejecting its `Invite(EmbargoEvent)`.

## Decision Outcome

Chosen option: "The owner adds, rejects and removes the embargo; each decision names the proposal it answers", because it is the only option in which every shape keeps one meaning without reading the sender, and in which the verb says what the decision does.

1. **Participants answer invitations; the case owner acts on embargoes.**
   `Accept(Invite(EmbargoEvent))` and `Reject(Invite(EmbargoEvent))` are always the sender's own consent, the case owner's included (ADR-0122, unchanged).
   The case owner's decisions for the case act on the `EmbargoEvent` itself.
2. **Activation is `Add(EmbargoEvent, target=VulnerabilityCase)`.**
   The case gains the embargo, so the activity that puts it in force is an `Add`, as the activity that ends it is a `Remove`.
   It replaces `Accept(EmbargoEvent, target=VulnerabilityCase)`.
   Its register step and consent effects are those ADR-0122 gives activation: `ACTIVATE`, `SUPERSEDE` of any `ACTIVE` entry, and `CARRY_OVER` for a revision that ends no later than the embargo it replaces.
   It also records the owner's `AGREE` when the owner's row holds no answer it gave: `UNINVITED`, `INVITED` or `TIMED_OUT`.
   An `AGREED` row is left as it is.
   The owner need not accept a proposal before it activates it.
3. **An owner that declined a proposal accepts it before it activates it.**
   An activation from an owner whose row for the proposal is `DECLINED` is refused before it is committed, and the refusal tells the owner to accept the invitation first.
   The consistent order is `Reject(Invite(EmbargoEvent))`, `Accept(Invite(EmbargoEvent))`, then the `Add`, and the ledger records each answer as it was given.
   This replaces ADR-0122's rule that a declined owner may still activate, its row moving straight to `AGREED`.
4. **Rejection stays `Reject(EmbargoEvent, target=VulnerabilityCase)`.**
   It is the owner's decision for the case, so it keeps a shape of its own and does not share the participant's `Reject(Invite(EmbargoEvent))`.
   The owner can still decline a proposal for itself, with `Reject(Invite(EmbargoEvent))`, and leave the case's decision open.
   Its own answer does not constrain the rejection: an owner that accepted terms for itself may still reject them for the case.
5. **Each owner decision on a proposal names that proposal in `inReplyTo`.**
   The `Add` and the `Reject` name the `Invite(EmbargoEvent)` that proposed the embargo they decide.

### Consequences

- Good, because a case change and a consent are different verbs, so a receiver tells them apart by type, not by the shape of the object.
- Good, because the case's embargo is put in force and ended by a matching pair, `Add` and `Remove`.
- Good, because a reader of either owner decision reaches the proposal it decided through `inReplyTo`.
- Good, because no handler reads the sender to learn what an activity means, so ADR-0122's driver holds.
- Good, because the owner's recorded answer and its decision for the case never contradict each other: a decline is changed only by the owner's own `Accept`.
- Bad, because an owner that declined and then changes its mind sends two activities, the `Accept` and the `Add`, where one would be unambiguous.
- Bad, because the wire format changes: the activation activity, its semantic type's pattern, the generated examples and the message reference pages all change.
- Bad, because activation and rejection no longer use matching verbs: `Add` puts an embargo in force, while `Reject` refuses one that never was.
- Neutral, because ADR-0152's rule of one semantic type per shape, whoever sends it, holds unchanged: no participant act has the shape of `Add(EmbargoEvent, target=VulnerabilityCase)` or `Reject(EmbargoEvent, target=VulnerabilityCase)`, so each owner decision keeps a semantic type of its own.

## Validation

The implementation is confirmed when the activation activity is an `Add` with `target` naming the case, no `Accept(EmbargoEvent, target=VulnerabilityCase)` shape remains in the vocabulary or its patterns, the tests that build both owner decisions find `inReplyTo` naming the proposal's `Invite(EmbargoEvent)`, and an activation from an owner whose row is `DECLINED` is refused with nothing committed.

## Pros and Cons of the Options

### Keep `Accept`/`Reject(EmbargoEvent, target=VulnerabilityCase)` and add `inReplyTo` only

- Good, because it is the smallest change: only `inReplyTo` is added.
- Bad, because activation still reads as an answer, told apart from a participant's consent only by the shape of its object.

### The owner adds, rejects and removes the embargo; each decision names the proposal it answers

- Good, because each shape keeps one meaning, and the verb says what the decision does.
- Bad, because activation and rejection are not a matching pair of verbs.

### The owner adds the embargo, and rejects a proposal by rejecting its `Invite(EmbargoEvent)`

- Good, because the rejection names the proposal as its `object`, so its reply link is natural.
- Bad, because `Reject(Invite(EmbargoEvent))` would mean the owner's decision for the case when the owner sends it and the sender's own decline from anyone else. That is the sender-switched meaning ADR-0122 retired for both owner decisions (MSM-07-003, MSM-07-004).
- Bad, because the owner could no longer decline a proposal for itself and leave the case's decision open: any decline from the owner would close the proposal.

## More Information

This record partially supersedes [ADR-0122](0122-per-embargo-participant-consent.md): it replaces the activation activity in ADR-0122's table of register and consent effects and in its table of register steps, refuses an activation from an owner that declined the proposal, and adds `inReplyTo` to both owner decisions.

A proposer cannot decline its own proposal and then activate it: it receives no invitation to its own proposal, so its `Reject(Invite(EmbargoEvent))` is refused, and it withdraws a proposal with `Undo(Invite(EmbargoEvent))` ([ADR-0152](0152-a-case-managers-act-shares-the-participants-semantic-type-and-an-observation-is-not-ledgered.md)).

Whether the owner may delegate the `Add` to the CASE_MANAGER, as it may delegate ending an embargo ([ADR-0118](0118-pec-expired-and-unbound-exited-states.md)), is an open question of the specification; if it is allowed, only an owner row that is `AGREED` authorizes it.
ADR-0122's other decisions stand.
