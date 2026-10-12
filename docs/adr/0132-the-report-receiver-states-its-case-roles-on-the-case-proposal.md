---
status: proposed
date: 2026-10-12
created: 2026-10-12
updated: 2026-10-12
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0041, ADR-0073; specs/case-proposal.yaml CP-01-010,
  CP-09-007, CP-09-008; specs/configuration.yaml CFG-07-002
informed: []
stakeholder_type: [project-contributor]
---

# The Report Receiver States Its Case Roles on the Case Proposal

## Context and Problem Statement

When the CASE_MANAGER accepts a `Create(as_CaseProposal)`, it seats the report receiver as the case's CASE_OWNER.
CP-09-007 says the receiver's other CVD roles come from `ActorConfig.default_case_roles`, and CFG-07-002 defines that field as the roles *the local actor* assumes when it owns a case.
The CASE_MANAGER read its own process's configuration to get them.

That worked only because the CaseActor ran in the report receiver's container, so "its own configuration" was the receiver's.
Once every container proposes to the dedicated case-actor container (#1876, DEMOMA-06-004), the CaseActor reads a configuration that says nothing about the receiver.
A Vendor that receives a report is then seated with `CASE_OWNER` alone, and its first fix-readiness report is refused because `CVDRole.VENDOR` is required for the `F` transition (ADR-0075).
Every Docker scenario in which a Vendor receives the report failed for this reason.

How should the receiver's roles reach the CASE_MANAGER?

## Decision Drivers

- The roles are the receiver's own fact, set in the receiver's configuration (CFG-07-002); they must not be inferred (CP-09-008).
- The CASE_MANAGER cannot read another actor's configuration or store (ADR-0073); whatever it needs has to arrive on the wire.
- The owner should hold its roles from the moment the case exists, so no window opens in which its own legitimate transitions are refused.
- A participant must not be able to grant itself `CASE_MANAGER`.

## Considered Options

- The receiver states its roles on the proposal
- The receiver claims its roles in a later message, after it joins
- The CASE_MANAGER is configured with the roles of every actor that may propose to it

## Decision Outcome

Chosen option: "The receiver states its roles on the proposal", because it is the only option that keeps the roles where CFG-07-002 puts them, the receiver's own configuration, and still has them in place when the case is created.

The report receiver copies its `default_case_roles` onto `as_CaseProposal` as `proposerCaseRoles`.
The parse edge refuses a proposal that claims `CASE_MANAGER`, because that role belongs only to the CaseActor.
The CASE_MANAGER seats the receiver with those roles plus `CASE_OWNER`, and uses its own configuration only for what is its own, such as the protocol default embargo.
This follows the same route as the receiver's embargo policy, which the CASE_MANAGER reads from the proposer's inline profile and nowhere else (CP-01-010).

### Consequences

- Good, because the CASE_MANAGER no longer depends on running in the receiver's container to seat it correctly.
- Good, because the owner's roles are in the bootstrap `Create(VulnerabilityCase)`, so every replica sees them from the first message.
- Bad, because the roles are the sender's claim, and the CASE_MANAGER does not check them against any other source; the prototype admits a proposal from any sender (#812).
- Neutral, because a proposal without the field seats the receiver as `CASE_OWNER` only, which is what a receiver with no `default_case_roles` gets today.

### Confirmation

The FV, FVV, FVCV-extension and FVCV-handoff Docker scenarios pass with the dedicated case-actor container.
Tests confirm three behaviours: the proposal carries the sender's `default_case_roles`, the CASE_MANAGER seats the owner with them, and a proposal that claims `CASE_MANAGER` is refused at parse.

## Pros and Cons of the Options

### The receiver states its roles on the proposal

- Good, because the roles come from the receiver's own configuration, as CFG-07-002 intends.
- Good, because no extra round trip is needed.
- Bad, because it adds a field to the proposal's wire form.

### The receiver claims its roles in a later message, after it joins

- Good, because the proposal's wire form is unchanged.
- Bad, because the owner holds no `VENDOR` role until the second message is committed, so a fix-readiness report sent in that window is refused.
- Bad, because the protocol has no message for a participant to add roles to itself, and adding one opens the same self-grant question with less context.

### The CASE_MANAGER is configured with the roles of every actor that may propose to it

- Good, because nothing on the wire changes.
- Bad, because it moves an actor's own fact into another actor's configuration, which goes stale as soon as either changes.
- Bad, because a CaseActor serves every case, so its configuration would have to list every possible receiver.

## More Information

Source: #1876, the move of every Docker scenario to the dedicated case-actor container.
Requirements: `specs/case-proposal.yaml` CP-01-011, CP-01-012 and the revised CP-09-007.
