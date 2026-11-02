---
status: accepted-provisional
date: 2026-11-02
created: 2026-11-02
updated: 2026-11-02
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0107, ADR-0132, ADR-0157; issues #5373, #5470;
  specs/case-bootstrap-trust.yaml CBT-01, CBT-05; specs/actor-knowledge-model.yaml
  AKM-05-007
informed: []
stakeholder_type: [project-contributor]
---

# The Bootstrap Create Carries Its Case and Nested Objects Inline

## Context and Problem Statement

A participant seeds its replica of a case from the bootstrap `Create(VulnerabilityCase)`.
The protocol let that message carry the case, and each object nested in it, inline or by reference.
A separate protocol rule says a receiver fetches an object it lacks and needs from the actor that holds it.

Read together, the two rules ask a receiver to fetch part of the bootstrap from someone.
The only candidate source is the CASE_MANAGER the message introduces, and the receiver does not trust it until it accepts this very message.
The reference implementation already refused a bootstrap that named a participant only by URI, and its specs called that refusal a shortcut of the prototype (#5373).

Should the bootstrap be allowed to carry a reference, so that a receiver must fetch it, or must it carry everything inline?

## Decision Drivers

- A receiver must be able to seed a complete replica from a message it can check.
- A receiver must not fetch from a source before it trusts that source.
- The protocol should not require a behavior its reference implementation does not have.
- Other implementations share the wire, so the rule must say what a receiver may refuse.

## Considered Options

- A. The bootstrap carries its case and every nested object inline, and a receiver does not fetch any of them.
- B. The bootstrap may name an object by reference, and the receiver fetches it from the CASE_MANAGER the message names.
- C. The bootstrap may name an object by reference, and the receiver fetches it from the sender.

## Decision Outcome

Chosen option: "A", because it is the only option in which a receiver never has to trust a source before the message that establishes trust.

The invariant is:

- The bootstrap `Create(VulnerabilityCase)` carries the complete case and every domain object nested in it inline.
- A receiver does not fetch an object the protocol requires inline.
  A bootstrap whose participant record is missing or named only by reference is a protocol error, and the receiver refuses it.

The CASE_MANAGER's own `Create(VulnerabilityCase)` to the Case Owner, which the Case Owner seeds from before it trusts the CASE_MANAGER, carries its participant records inline for the same reason.
Every other message keeps the general rule: an object may travel inline or by reference, and a receiver fetches what it lacks and needs.

### Consequences

- Good, because the trust root no longer depends on a fetch from an actor the receiver does not yet trust.
- Good, because the protocol now states the refusal the reference implementation already performs, so the refusal is no longer a prototype shortcut.
- Good, because the receiver's checks run on one message, with nothing left to fetch.
- Bad, because a large case makes a large bootstrap message.
- Neutral, because the receiver's refusal covers participant records, which its later checks read; a report the receiver already holds, such as the one it submitted, it can still read from its own store if a non-conforming sender names it by reference.
- Neutral, because a `Create` whose own `object` is a bare URI cannot be recognised as a bootstrap until its type is known, and a receiver that holds no case has no host to fetch it from, so it is not processed.

## Validation

- A test sends a bootstrap whose participant is a bare URI and finds it refused before anything is stored.
- A test checks that the bootstrap a sender builds carries the case, its participants and its reports as full objects.
- A test gives a sender a case naming a participant its own store cannot read and finds the bootstrap is not sent.

## Pros and Cons of the Options

### A. Everything inline

- Good, because the receiver needs no second source.
- Good, because it matches what the reference implementation sends and accepts.
- Bad, because the message grows with the case.

### B. Fetch from the CASE_MANAGER

- Good, because the bootstrap message stays small.
- Bad, because the receiver must ask the CASE_MANAGER before it trusts it, and a forged bootstrap could point it at a forged one.
- Bad, because the CASE_MANAGER's read serves only participants of the case, and the receiver is not one until it accepts the bootstrap.

### C. Fetch from the sender

- Good, because the sender is the actor the reporter chose.
- Bad, because the sender may have delegated the case to another CASE_MANAGER and need not hold every object.
- Bad, because it adds a fetch exchange that exists only for the bootstrap.

## More Information

Generated spec requirements: `case-bootstrap-trust.yaml` CBT-01-002, CBT-01-007; `actor-knowledge-model.yaml` AKM-05-007; `case-proposal.yaml` CP-09-004.
