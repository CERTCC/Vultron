---
status: proposed
date: 2026-10-01
created: 2026-10-01
updated: 2026-10-01
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; CONCERN-3733; ADR-0095, ADR-0109, ADR-0114;
  specs/handler-protocol.yaml HP-00, HP-01;
  specs/case-management.yaml CM-10, CM-11, CM-16, CM-21;
  specs/case-proposal.yaml CP-06;
  specs/sync-ledger-replication.yaml SYNC-03;
  specs/participant-case-replica.yaml PCR-03
informed: []
stakeholder_type: [project-contributor]
---

# Received Handlers Check the Sender's Entitlement, Declared Once per Use Case and Composed by the Receive-Tree Factory

## Context and Problem Statement

A received activity is an assertion about its sender's state (HP-00-001).
Before a handler applies it, someone has to ask whether that sender may make it.
For many handlers nobody asks.
While classifying every received handler's exit as applied, skipped, deferred or refused (#2255), CONCERN-3733 found handlers that change another actor's replica for any sender.
An actor can claim case ownership, admit itself to a case with roles it chooses, remove notes, attach reports, redirect a vendor's trust in its case manager, and obtain the full case and ledger by rejecting a ledger entry.

Every CASE_MANAGER gate in these trees checks the *receiver's* role (BT-17-001).
None checks the sender.
Sender checks do exist, but in seven near-duplicate forms spread across `behaviors/` and `use_cases/`.
They are composed by the handlers that happen to have one, and nothing shows which handlers lack one.

Where should the sender check live, and how do we keep it from drifting again?

## Decision Drivers

- The entitlement differs per message.
  Depending on the message, the sender must be the named transferee of a pending Offer, the invitee of a recorded Invite, the actor a proposal was addressed to, the Case Owner, an active participant, or the CASE_MANAGER.
- Two legitimate senders are not active participants: an invitee answering its stub Invite, and a case manager answering a vendor's case proposal, where the vendor has no case yet.
- One implementation, composed everywhere (CS-22-001): no handler-local predicate, and no twin module.
- A handler that is missing a check must be found by a test, not by the next audit.
- Receive-side ordering stays intake, then guards, then commit, then effects (CLP-10-006, ADR-0111).

## Considered Options

- A guard per handler, built from one shared sender-entitlement module, declared once per received use case and composed by the receive-tree factory
- One check before dispatch that the sender is a participant
- A check before dispatch plus per-handler guards

## Decision Outcome

Chosen option: "A guard per handler, built from one shared module, declared once per use case and composed by the receive-tree factory", because only a per-message rule can name the right entitlement, and a declaration that the factory reads and a ratchet checks keeps the rule in one place.

1. **One sender-entitlement module.**
   It holds the sender predicates and a thin condition node for each.
   The existing sender checks merge into it, and their old homes are retired.
2. **One declaration per received use case.**
   Each received use case declares either an entitlement kind or an exemption with a written reason.
   The declaration is the only place a handler states who may send it.
3. **The receive-tree factory composes the guard.**
   `create_receive_activity_tree` reads the declaration and puts the matching guard in the guard stage, ahead of the guarded commit.
   A failed guard ends the tree with `REFUSED` and a reason naming the missing entitlement (HP-01-006), with nothing written and nothing sent.
4. **A ratchet enforces coverage.**
   An architecture test walks `SEMANTIC_REGISTRY` and fails on any received use case with no declaration, and on any sender predicate defined outside the module.
   A handler not yet fixed is declared exempt with a reason naming its tracking issue, so the remaining gap is a list in code.
5. **Being in the roster is not entitlement.**
   Where a message requires a participant, the participant must be active (CM-10-004).
   The rule that authority to act follows the same active-participant predicate as entitlement to case content is decided and recorded by #2257, which maintains ADR-0114's joining model.
   A reply to an ask is authorized by the ask naming its sender, not by membership.
6. **A replica accepts case-state changes only from the CASE_MANAGER** (PCR-03-001).
   A sender clause names what the CASE_MANAGER checks, and replicas check that the sender is the CASE_MANAGER.

### Consequences

- Good, because each message names one entitlement in one place, and a missing check fails a test.
- Good, because the seven existing sender checks become one.
- Good, because the CASE_MANAGER gate keeps its meaning as a receiver check, and the sender check stands beside it rather than being inferred from it.
- Bad, because every received use case gains a declaration, including those that are exempt.
- Bad, because a handler built outside `create_receive_activity_tree` gets no guard from the factory.
  The Remove(Note) and Add(Report) handlers move onto the factory as part of their fix (#4074); the add/remove participant handlers do so under #2257.

## Validation

- An architecture ratchet under `test/architecture/` fails on a received use case with no entitlement declaration and on a sender predicate outside the module (HP-01-007).
- Each per-message sender clause (CM-11-017, CM-16-019, CM-21-011, CM-30-001, CM-30-002, CP-06-005, SYNC-03-005) has a marked test that sends the message from an unentitled sender and asserts `REFUSED` with no protocol effect and an empty outbox.

## Pros and Cons of the Options

### A guard per handler, declared once and composed by the factory

- Good, because each message checks the entitlement that is right for it.
- Good, because the declaration gives the ratchet one thing to read.
- Neutral, because each handler still needs its own fix, but the fix is a declaration plus at most one new predicate.

### One check before dispatch that the sender is a participant

- Good, because there is only one call site.
- Bad, because it wrongly refuses an invitee's Accept and a case manager's reply to a case proposal unless those two are carved out.
- Bad, because "is a participant" is the wrong question for ownership transfer, recommendations and Remove(Note), so those handlers still need their own checks.

### A check before dispatch plus per-handler guards

- Good, because it is defense in depth.
- Bad, because the participant rule lives in two places and needs an exemption list of its own.

## More Information

- CONCERN-3733 lists the handlers and what an unentitled sender achieves at each.
- ADR-0095 introduced `REFUSED` and the received-side `HandlerResult`.
- ADR-0114 separates roster membership from being an active participant.

Generated spec requirements: `handler-protocol.yaml` HP-01-006, HP-01-007; `case-management.yaml` CM-11-017, CM-16-019, CM-21-011, CM-30-001, CM-30-002; `case-proposal.yaml` CP-06-005; `sync-ledger-replication.yaml` SYNC-03-005.
