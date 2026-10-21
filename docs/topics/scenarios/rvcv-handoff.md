---
title: "RVCV-handoff Scenario: Reporter + Vendor1 → Coordinator + Vendor2"
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
      The Case Actor makes and records the ownership offer Vendor1 proposed
      before it reaches the Coordinator (ADR-0148); the Coordinator's
      acceptance follows the recorded offer.
  - antecedent: report_submitted
    consequent: validate_report
    consequent_actor: vendor
    observable: false
    note: >
      Report submission by the Reporter is an out-of-band API call that
      precedes the case.
stakeholder_type: [platform-developer, project-contributor]
level: 300
---

# RVCV-handoff Scenario: Reporter + Vendor1 → Coordinator + Vendor2

## Overview

The RVCV-handoff scenario demonstrates **case-ownership transfer** from Vendor1
to a Coordinator.  The Reporter reports to Vendor1.  Vendor1 creates and initially
owns the case.  Vendor1 then invites a Coordinator and transfers ownership to
the Coordinator.  The Coordinator, now the case owner, invites Vendor2.  Both
vendors develop fixes before joint disclosure.

**Participants:**

- **Reporter** — discovers the vulnerability and submits the report; in the case it holds the Reporter role; the protocol has no separate Finder role ([ADR-0078](../../adr/0078-retire-finder-role.md)).
- **Vendor1** — receives the report; validates and engages the case; holds initial ownership; transfers ownership to the Coordinator.
- **Coordinator** — joins via Vendor1's invitation; receives case ownership; invites Vendor2.
- **Vendor2** — joins via the Coordinator's invitation; develops and ships a fix.
- **Case Actor** — the actor that holds the [CASE_MANAGER](../case_lifecycle/case_manager_and_ledger.md) role for this case; it writes every canonical ledger entry and fans it out to the participants. In the demo it runs on the dedicated `case-actor` container, but its authority comes from the role, not from where it runs; the same Case Actor keeps the role after the ownership handoff.

## Protocol narrative

### 1. Reporter submits a vulnerability report to Vendor1

The Reporter reports to Vendor1's endpoint.  No ledger entry is created yet.

*Antecedent:* Reporter has knowledge of the vulnerability.

### 2. Vendor1 validates and engages the case

Vendor1 reviews the report and accepts it.  `validate_report` and `engage_case`
entries appear in the ledger.

*Antecedent:* Report received from Reporter.

### 3. Participant status records are created

The Case Actor records the engagement's status as an `add_participant_status_to_participant` entry; each record seated at case creation was ledgered as a `create_case_participant` entry.

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
Vendor1 proposes the transfer to the **Case Actor**, not to the Coordinator (ADR-0053, ADR-0148).
The Case Actor makes the offer itself, under its own identity, and records it as an `offer_case_ownership_transfer` entry, so every participant learns that a transfer is on offer.
The offer the Coordinator receives is the Case Actor's own, with an identity the Case Actor derived from Vendor1's proposal.

*Antecedent:* Coordinator's `accept_invite_actor_to_case` entry is in the ledger.

### 7. Coordinator accepts case ownership

The Coordinator formally accepts the ownership transfer, addressing the acceptance to the Case Actor.
The Case Actor commits an `accept_case_ownership_transfer` ledger entry and applies the role change: the `CASE_OWNER` role moves from Vendor1 to the Coordinator, and the case's `attributed_to` field is updated to the Coordinator.
Each of those changes follows as its own Case Actor entry (`update_case_participant` for each participant record, then `update_case_owner` for the case), and every entry is broadcast to **every** participant.
That broadcast is how the Reporter, who is neither the old nor the new owner, learns who is now responsible for the case.

*Antecedent:* the Case Actor's ownership offer has reached the Coordinator.

### 8. Coordinator invites Vendor2

The Coordinator, now the case owner, identifies Vendor2 as affected and sends
a second `invite_actor_to_case` entry.

*Antecedent:* `accept_case_ownership_transfer` is in the ledger (the Coordinator must own the case before inviting others as its owner).

### 9. Vendor2 accepts the invitation

Vendor2 reviews and accepts.  An `accept_invite_actor_to_case` entry is recorded.

*Antecedent:* The Coordinator's `invite_actor_to_case` entry is in the ledger.

### 10. Participants exchange notes

All participants communicate through case notes.
Each note is sent as one `Add(Note)` carrying the note inline, and recorded as an `add_note_to_case` entry, which attaches it to the case.

*Antecedent:* `engage_case` is in the ledger.

### 11. Both vendors reach fix-ready

Vendor1 and Vendor2 each advance to VFd (fix-ready) status.

*Antecedent:* `engage_case` is in the ledger.

### 12. Participants publish; embargo terminates

All participants publish.  The embargo exits ACTIVE.

*Antecedent:* At least one vendor has reached fix-ready.

### 13. All participants close the case

`close_case` entries appear for each participant.
Vendor1, Vendor2, and the Reporter leave first; the Coordinator, the Case Owner since the handoff, leaves last.
A departure sent after the owner's is not recorded, so every other participant's departure is recorded first.

*Antecedent:* `validate_report` and `engage_case` are in the ledger.

## Unobservable edges

| Unobservable step | Why not in ledger |
|---|---|
| Reporter submits report to Vendor1 | Report submission precedes the case. |

The ownership offer is not an unobservable step.
The Case Actor records it as `offer_case_ownership_transfer` once it sends the offer, and the Coordinator's `accept_case_ownership_transfer` follows it, which is the edge declared above.
