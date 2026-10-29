---
status: accepted-provisional
date: 2026-10-29
created: 2026-10-29
updated: 2026-10-29
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0107, ADR-0148, ADR-0159; issues #5395, #5439;
  specs/actor-knowledge-model.yaml AKM-02-004, AKM-03-003;
  specs/case-management.yaml CM-21-021
informed: []
stakeholder_type: [project-contributor]
---

# A Participant's Act on a Case Names the Case and Never Carries It

## Context and Problem Statement

Four messages a participant sends to the case's CASE_MANAGER carried the participant's whole replica of the case as their `object`.
They are the RA `Join(VulnerabilityCase)`, the RD `Ignore(VulnerabilityCase)`, the RC `Leave(VulnerabilityCase)`, and the ownership-transfer proposal `Offer(Offer(VulnerabilityCase))`.
No handler of them reads anything from that copy but the case id: the CASE_MANAGER holds the canonical case and reads it first.

The CASE_MANAGER records a received act's body verbatim in its ledger (CLP-07-011, ADR-0107), so every replica received the participant's copy too.
A replica that reflects an entry copies the notes, statuses and embargoes the entry carries and its own case names, so a participant's copy could put its own view of those records into every replica.
A participant's copy can disagree with the canonical case.

How should a participant's act on a case name the case?

## Decision Drivers

- The CASE_MANAGER's copy is the only case on the ledger.
- A receiver routes an activity by its object's `type`, so the object must carry a `type` it can read without a fetch.
- Nothing travels that the receiver does not need: every receiver of these acts already holds the case.
- A message another sender still builds the old way is still understood (Postel).

## Considered Options

- **A typed case reference.** The `object` is an inline object with only the case's `id` and `type`.
- **A bare case URI.** The `object` is the case id as a string.
- **Keep the copy, and ignore it.** The `object` stays the full case; receivers read only its id.

## Decision Outcome

Chosen option: **A typed case reference**, because it is the only option that keeps type-based routing and puts no copy of the case on the ledger.

A participant's act on a case names the case and never carries it.
The case travels as `{"id": <case id>, "type": "VulnerabilityCase"}`, the same shape as an actor reference (ADR-0159).
The receiver reads only the id and takes every detail from the case it holds.

A full case that another sender still carries in one of these acts is not refused.
The receiver reads only its id, ignores everything else in it, and stores nothing from it: no replica copies a record out of the case such an act carries.
A case id the receiver does not hold leaves it nothing to act on, so the act is refused, naming the activity and the case.

### The ownership-transfer Offer, layer by layer

The ownership transfer (ADR-0148) has these layers, and each one's receiver holds the case:

1. **The owner's proposal**, `Offer(Offer(VulnerabilityCase), context=case)`, goes to the CASE_MANAGER.
   Its `object` is the inner Offer, an activity, which stays inline as the template of the Offer the CASE_MANAGER makes.
   Its `context` already names the case by URI.
2. **The inner Offer's object** is the case, and its receiver is the CASE_MANAGER, which holds the canonical case.
   It becomes a typed reference.
3. **The CASE_MANAGER's own `Offer(VulnerabilityCase)`** goes to the transferee and is ledgered, so every replica receives it.
   The transferee must be an active participant both when the owner proposes and when it accepts (CM-21-021), so it has joined the case and holds it; every replica holds the case by being one.
   It becomes a typed reference, built by the same factory as the inner Offer.
4. **The transferee's `Accept` or `Reject`** embeds the CASE_MANAGER's Offer as it was received, so it carries the reference.
5. **The owner's `Undo`** embeds its own proposal, so it carries the reference too.

No layer goes to an actor that may lack the case, so no layer keeps carrying it.

### Consequences

- Good, because the ledger carries only the CASE_MANAGER's case, so no replica can take a participant's view of a record from it.
- Good, because the acts carry no case content, so they disclose nothing the receiver does not already hold.
- Good, because a receiver still routes each act by its object's `type`.
- Good, because the CASE_MANAGER no longer needs to check or hold an embargo carried in a Join.
- Neutral, because AKM-03-003, which asks for every `object` to be fully inline, gains an exception for these acts.
- Bad, because a body built the old way still reaches the ledger verbatim, so the rule that no record is copied out of such a body has to be kept by every replica.

## Validation

- Factory tests assert that each of the four acts carries exactly the typed reference.
- Received-side tests deliver a typed reference, a full case whose details disagree with the canonical case, and an unknown case id, and assert the canonical case is used, nothing is stored and the unknown case is refused.
- A ledger test commits each act at the CASE_MANAGER and asserts the entry's snapshot carries only the reference, and that a replica applying it gains no record from it.

## Pros and Cons of the Options

### A typed case reference (chosen)

- Good, because it routes by `type` and carries nothing else.
- Good, because it is the shape an actor reference already has.
- Bad, because the parser has to tell a reference from a sparse case, which it does by the reference carrying no key but `id` and `type`.

### A bare case URI

- Good, because it is the smallest form.
- Bad, because a pattern can no longer tell `Offer(VulnerabilityCase)` from `Offer(VulnerabilityReport)` by the object's type, so every pattern of these verbs would need a bare-object exception (SE-01-006).

### Keep the copy, and ignore it

- Good, because no wire shape changes.
- Bad, because the participant's copy still reaches every replica through the ledger.
- Bad, because the acts keep sending case content nobody reads.

## More Information

The other by-reference object, `Read(CaseLedgerEntry)` (SYNC-17-001), names its entry by bare id and is matched through `accepts_bare_object`; the typed reference keeps the patterns here matching by type instead.
ADR-0148 decided who may be offered ownership of a case; this record only changes how its Offer names the case, and option T4 there is what makes every receiver one that holds it.
