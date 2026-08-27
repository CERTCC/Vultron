---
title: "FVCV-handoff Scenario: Finder + Vendor1 → Coordinator + Vendor2"
status: stable
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
    consequent_actor: vendor
    note: >
      Vendor1 invites the Coordinator after the case is active.
  - antecedent: invite_actor_to_case
    consequent: accept_invite_actor_to_case
    consequent_actor: coordinator
    note: >
      The Coordinator accepts Vendor1's invitation; acceptance follows the invite.
  - antecedent: accept_invite_actor_to_case
    consequent: invite_actor_to_case
    consequent_actor: coordinator
    note: >
      After the ownership transfer, the Coordinator (as new case owner) invites
      Vendor2.  This second invite follows the Coordinator's own acceptance.
  - antecedent: validate_report
    consequent: close_case
    consequent_actor: coordinator
    note: >
      Closure requires a validated, engaged case.  After the handoff, the
      Coordinator is the case owner and commits the last close entry.
  - antecedent: engage_case
    consequent: add_note_to_case
    consequent_actor: vendor
    note: >
      Notes require an active case.
  - antecedent: report_submitted
    consequent: validate_report
    consequent_actor: vendor
    observable: false
    note: >
      Report submission by the Finder is an out-of-band API call that
      precedes the case.
---

# FVCV-handoff Scenario: Finder + Vendor1 → Coordinator + Vendor2

## Overview

The FVCV-handoff scenario demonstrates **case-ownership transfer** from Vendor1
to a Coordinator.  The Finder reports to Vendor1.  Vendor1 creates and initially
owns the case.  Vendor1 then invites a Coordinator and transfers ownership to
the Coordinator.  The Coordinator, now the case owner, invites Vendor2.  Both
vendors develop fixes before joint disclosure.

**Participants:**

- **Finder** — discovers the vulnerability; submits the initial report.
- **Vendor1** — receives the report; validates and engages the case; holds initial ownership; transfers ownership to the Coordinator.
- **Coordinator** — joins via Vendor1's invitation; receives case ownership; invites Vendor2.
- **Vendor2** — joins via the Coordinator's invitation; develops and ships a fix.
- **CaseActor** — Vendor1's internal case-management sub-actor (remains the same sub-actor after the handoff).

## Protocol narrative

### 1. Finder submits a vulnerability report to Vendor1

The Finder reports to Vendor1's endpoint.  No ledger entry is created yet.

*Antecedent:* Finder has knowledge of the vulnerability.

### 2. Vendor1 validates and engages the case

Vendor1 reviews the report and accepts it.  `validate_report` and `engage_case`
entries appear in the ledger.

*Antecedent:* Report received from Finder.

### 3. Participant status records are created

The CaseActor records initial `add_participant_status_to_participant` entries.

*Antecedent:* `engage_case` is in the ledger.

### 4. Vendor1 invites the Coordinator

Vendor1 sends the Coordinator an `invite_actor_to_case` entry.

*Antecedent:* `engage_case` is in the ledger.

### 5. Coordinator accepts the invitation

The Coordinator joins the case.  An `accept_invite_actor_to_case` entry is
recorded.

*Antecedent:* `invite_actor_to_case` is in the ledger (step 4).

### 6. Vendor1 offers case ownership to the Coordinator

Vendor1 decides that the Coordinator is better positioned to manage the case
and initiates a case-ownership transfer.  This is an implementation-level
protocol step; the consequent observable entry is the Coordinator's acceptance.

*Antecedent:* Coordinator's `accept_invite_actor_to_case` entry is in the ledger.

### 7. Coordinator accepts case ownership

The Coordinator formally accepts the ownership transfer.  The case's
`attributed_to` field is updated to the Coordinator.

*Antecedent:* Vendor1's ownership offer has been delivered to the Coordinator.

### 8. Coordinator invites Vendor2

The Coordinator, now the case owner, identifies Vendor2 as affected and sends
a second `invite_actor_to_case` entry.

*Antecedent:* The Coordinator's `accept_invite_actor_to_case` entry is in the
ledger (the Coordinator must have joined before inviting others).

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

`close_case` entries appear for each participant.  The Coordinator, as the
current case owner, commits the final close entry.

*Antecedent:* `validate_report` and `engage_case` are in the ledger.

## Unobservable edges

| Unobservable step | Why not in ledger |
|---|---|
| Finder submits report to Vendor1 | Report submission precedes the case. |
| Vendor1 offers ownership transfer | The offer itself is a protocol message, not a case-ledger entry; only the Coordinator's `accept_case_ownership_transfer` appears in the ledger in the FCCV-handoff variant. In this scenario the ownership acceptance step may also produce an `accept_case_ownership_transfer` entry; the causal edge from the acceptance to the Coordinator's subsequent invite is captured via the `accept_invite_actor_to_case → invite_actor_to_case` edge above. |
