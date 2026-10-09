---
title: "FVCV-handoff Scenario: Finder + Vendor1 → Coordinator + Vendor2"
causal_edges:
  - antecedent: validate_report
    consequent: engage_case
    consequent_actor: vendor
    note: >
      Vendor1 validates and then engages the case.
  - antecedent: engage_case
    consequent: add_participant_status_to_participant
    consequent_actor: case-actor
    note: >
      Case engagement triggers participant status entries.
  - antecedent: engage_case
    consequent: invite_actor_to_case
    consequent_actor: case-actor
    note: >
      Vendor1 invites the Coordinator after the case is active.
  - antecedent: invite_actor_to_case
    consequent: accept_invite_actor_to_case
    consequent_actor: coordinator
    note: >
      The Coordinator accepts Vendor1's invitation; acceptance follows the invite.
  - antecedent: accept_invite_actor_to_case
    consequent: accept_case_ownership_transfer
    consequent_actor: coordinator
    note: >
      The Coordinator accepts the ownership transfer from Vendor1 only after
      it has joined the case; the ownership-transfer acceptance must follow
      the Coordinator's participation acceptance.
  - antecedent: accept_case_ownership_transfer
    consequent: invite_actor_to_case
    consequent_actor: case-actor
    note: >
      As the new case owner, the Coordinator invites Vendor2.  This second
      invite must follow the ownership acceptance.
  - antecedent: invite_actor_to_case
    consequent: accept_invite_actor_to_case
    consequent_actor: vendor2
    note: >
      Vendor2 accepts the Coordinator's invitation; acceptance follows the
      invite.
  - antecedent: validate_report
    consequent: close_case
    consequent_actor: coordinator
    note: >
      Closure requires a validated, engaged case.  After the handoff, the
      Coordinator is the case owner and commits the last close entry.
  - antecedent: close_case
    consequent: close_case
    consequent_actor: coordinator
    note: >
      The Coordinator, the Case Owner, leaves last (CM-23-015): another
      participant's close_case precedes the owner's.  The owner's departure
      closes the case, and a departure sent after it is not recorded
      (CM-23-013).
  - antecedent: engage_case
    consequent: add_note_to_case
    consequent_actor: vendor
    note: >
      Notes require an active case.
  - antecedent: offer_case_ownership_transfer
    consequent: accept_case_ownership_transfer
    consequent_actor: coordinator
    note: >
      The Case Actor records Vendor1's ownership offer before forwarding it to
      the Coordinator (ADR-0053); the Coordinator's acceptance follows the
      recorded offer.
  - antecedent: report_submitted
    consequent: validate_report
    consequent_actor: vendor
    observable: false
    note: >
      Report submission by the Finder is an out-of-band API call that
      precedes the case.
stakeholder_type: [platform-developer, project-contributor]
level: 300
---

# FVCV-handoff Scenario: Finder + Vendor1 → Coordinator + Vendor2

## Overview

The FVCV-handoff scenario demonstrates **case-ownership transfer** from Vendor1
to a Coordinator.  The Finder reports to Vendor1.  Vendor1 creates and initially
owns the case.  Vendor1 then invites a Coordinator and transfers ownership to
the Coordinator.  The Coordinator, now the case owner, invites Vendor2.  Both
vendors develop fixes before joint disclosure.

**Participants:**

- **Finder** — discovers the vulnerability and submits the report; in the case it holds the Reporter role, because the protocol has no Finder role ([ADR-0078](../../adr/0078-retire-finder-role.md)).
- **Vendor1** — receives the report; validates and engages the case; holds initial ownership; transfers ownership to the Coordinator.
- **Coordinator** — joins via Vendor1's invitation; receives case ownership; invites Vendor2.
- **Vendor2** — joins via the Coordinator's invitation; develops and ships a fix.
- **Case Actor** — the actor that holds the [CASE_MANAGER](../case_lifecycle/case_manager_and_ledger.md) role for this case; it writes every canonical ledger entry and fans it out to the participants. Vendor1's platform hosts it, but its authority comes from the role, not from where it runs; the same Case Actor keeps the role after the ownership handoff.

## Protocol narrative

### 1. Finder submits a vulnerability report to Vendor1

The Finder reports to Vendor1's endpoint.  No ledger entry is created yet.

*Antecedent:* Finder has knowledge of the vulnerability.

### 2. Vendor1 validates and engages the case

Vendor1 reviews the report and accepts it.  `validate_report` and `engage_case`
entries appear in the ledger.

*Antecedent:* Report received from Finder.

### 3. Participant status records are created

The Case Actor records initial `add_participant_status_to_participant` entries.

*Antecedent:* `engage_case` is in the ledger.

### 4. Vendor1 invites the Coordinator

Vendor1 sends the Coordinator an `invite_actor_to_case` entry.

*Antecedent:* `engage_case` is in the ledger.

### 5. Coordinator accepts the invitation

The Coordinator joins the case.  An `accept_invite_actor_to_case` entry is
recorded.

*Antecedent:* `invite_actor_to_case` is in the ledger (step 4).

### 6. Vendor1 offers case ownership to the Coordinator

Vendor1 decides that the Coordinator is better positioned to manage the case and initiates a case-ownership transfer.
The offer is addressed to the **Case Actor**, not to the Coordinator (ADR-0053): the Case Actor records it as an `offer_case_ownership_transfer` entry, so every participant learns that a transfer is on offer, and then forwards an offer of its own to the Coordinator.
The offer the Coordinator receives is therefore a new activity with its own identity.

*Antecedent:* Coordinator's `accept_invite_actor_to_case` entry is in the ledger.

### 7. Coordinator accepts case ownership

The Coordinator formally accepts the ownership transfer, addressing the
acceptance to the Case Actor.  The Case Actor applies the role change — the
case's `attributed_to` field is updated to the Coordinator — then commits an
`accept_case_ownership_transfer` ledger entry and broadcasts it to **every**
participant.  That broadcast is how the Finder, who is neither the old nor the
new owner, learns who is now responsible for the case.

*Antecedent:* the Case Actor's forwarded ownership offer has reached the
Coordinator.

### 8. Coordinator invites Vendor2

The Coordinator, now the case owner, identifies Vendor2 as affected and sends
a second `invite_actor_to_case` entry.

*Antecedent:* `accept_case_ownership_transfer` is in the ledger (the Coordinator must own the case before inviting others as its owner).

### 9. Vendor2 accepts the invitation

Vendor2 reviews and accepts.  An `accept_invite_actor_to_case` entry is recorded.

*Antecedent:* The Coordinator's `invite_actor_to_case` entry is in the ledger.

### 10. Participants exchange notes

All participants communicate via `add_note_to_case` entries.

*Antecedent:* `engage_case` is in the ledger.

### 11. Both vendors reach fix-ready

Vendor1 and Vendor2 each advance to VFd (fix-ready) status.

*Antecedent:* `engage_case` is in the ledger.

### 12. Participants publish; embargo terminates

All participants publish.  The embargo exits ACTIVE.

*Antecedent:* At least one vendor has reached fix-ready.

### 13. All participants close the case

`close_case` entries appear for each participant.
Vendor1, Vendor2, and the Finder leave first; the Coordinator, the Case Owner since the handoff, leaves last.
A departure sent after the owner's is not recorded, so every other participant's departure is recorded first.

*Antecedent:* `validate_report` and `engage_case` are in the ledger.

## Unobservable edges

| Unobservable step | Why not in ledger |
|---|---|
| Finder submits report to Vendor1 | Report submission precedes the case. |

The ownership offer is not an unobservable step.
The Case Actor records it as `offer_case_ownership_transfer` before it forwards the offer, and the Coordinator's `accept_case_ownership_transfer` follows it, which is the edge declared above.
