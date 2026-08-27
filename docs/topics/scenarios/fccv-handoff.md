---
title: "FCCV-handoff Scenario: Finder + C1 → C2 + Vendor"
status: stable
causal_edges:
  - antecedent: validate_report
    consequent: engage_case
    consequent_actor: c1
    note: >
      C1 validates the report before engaging the case.
  - antecedent: engage_case
    consequent: add_participant_status_to_participant
    consequent_actor: case-actor
    note: >
      Case engagement triggers participant status entries.
  - antecedent: engage_case
    consequent: invite_actor_to_case
    consequent_actor: c1
    note: >
      C1 invites C2 after the case is active.
  - antecedent: invite_actor_to_case
    consequent: accept_invite_actor_to_case
    consequent_actor: c2
    note: >
      C2 accepts C1's invitation; acceptance follows the invite.
  - antecedent: accept_invite_actor_to_case
    consequent: accept_case_ownership_transfer
    consequent_actor: c2
    note: >
      C2 accepts the ownership transfer from C1 only after C2 has joined the
      case; the ownership-transfer acceptance must follow C2's participation
      acceptance.
  - antecedent: accept_case_ownership_transfer
    consequent: invite_actor_to_case
    consequent_actor: c2
    note: >
      As the new case owner, C2 invites the Vendor.  This invite must follow
      the ownership acceptance.
  - antecedent: invite_actor_to_case
    consequent: accept_invite_actor_to_case
    consequent_actor: vendor
    note: >
      The Vendor accepts C2's invitation; acceptance follows the invite.
  - antecedent: validate_report
    consequent: close_case
    consequent_actor: c2
    note: >
      Closure requires a validated, engaged case.  C2, as the post-handoff
      case owner, commits the final close entry.
  - antecedent: engage_case
    consequent: add_note_to_case
    consequent_actor: finder
    note: >
      Notes require an active case.
  - antecedent: report_submitted
    consequent: validate_report
    consequent_actor: c1
    observable: false
    note: >
      Report submission by the Finder is an out-of-band API call that
      precedes the case.
---

# FCCV-handoff Scenario: Finder + C1 → C2 + Vendor

## Overview

The FCCV-handoff scenario exercises **coordinator-to-coordinator case-ownership
transfer**.  The Finder reports to C1.  C1 creates and initially owns the case.
C1 invites C2, then transfers ownership to C2.  C2, now the case owner, invites
the Vendor.  All participants eventually disclose and close the case.

**Participants:**

- **Finder** — discovers the vulnerability; submits the initial report.
- **C1 (Coordinator 1)** — receives the report; validates and engages the case; transfers ownership to C2.
- **C2 (Coordinator 2)** — joins via C1's invitation; receives case ownership; invites the Vendor.
- **Vendor** — joins via C2's invitation; develops and ships a fix.
- **CaseActor** — C1's internal case-management sub-actor (retained after the handoff).

## Protocol narrative

### 1. Finder submits a vulnerability report to C1

The Finder reports to C1's endpoint.  No ledger entry is created yet.

*Antecedent:* Finder has knowledge of the vulnerability.

### 2. C1 validates and engages the case

C1 reviews the report and accepts it.  `validate_report` and `engage_case`
entries appear in the ledger.

*Antecedent:* Report received from Finder.

### 3. Participant status records are created

The CaseActor records initial `add_participant_status_to_participant` entries.

*Antecedent:* `engage_case` is in the ledger.

### 4. C1 invites C2

C1 sends C2 an `invite_actor_to_case` entry.

*Antecedent:* `engage_case` is in the ledger.

### 5. C2 accepts the invitation

C2 joins the case.  An `accept_invite_actor_to_case` entry is recorded.

*Antecedent:* `invite_actor_to_case` is in the ledger (step 4).

### 6. C1 offers case ownership to C2

C1 decides to transfer the case to C2 and initiates the ownership-transfer
protocol.  This is an exchange of protocol messages; the consequent observable
entry is C2's acceptance.

*Antecedent:* C2's `accept_invite_actor_to_case` entry is in the ledger.

### 7. C2 accepts case ownership

C2 formally accepts the ownership transfer.  An `accept_case_ownership_transfer`
entry is recorded.  The case's `attributed_to` field is updated to C2.

*Antecedent:* C1's ownership-transfer offer has been delivered to C2.

### 8. C2 invites the Vendor

C2, as the new case owner, identifies the Vendor as affected and sends an
`invite_actor_to_case` entry.

*Antecedent:* `accept_case_ownership_transfer` is in the ledger.

### 9. Vendor accepts the invitation

The Vendor reviews and accepts.  An `accept_invite_actor_to_case` entry is
recorded.

*Antecedent:* C2's `invite_actor_to_case` entry is in the ledger.

### 10. Participants exchange notes

All participants communicate via `add_note_to_case` entries.

*Antecedent:* `engage_case` is in the ledger.

### 11. Vendor reaches fix-ready

The Vendor advances to VFd (fix-ready) status.

*Antecedent:* `engage_case` is in the ledger.

### 12. Participants publish; embargo terminates

All participants publish.  The embargo exits ACTIVE.

*Antecedent:* Vendor has reached fix-ready.

### 13. All participants close the case

`close_case` entries appear for each participant.  C2, as the case owner,
commits the final close entry.

*Antecedent:* `validate_report` and `engage_case` are in the ledger.

## Unobservable edges

| Unobservable step | Why not in ledger |
|---|---|
| Finder submits report to C1 | Report submission precedes the case. |
| C1 offers ownership transfer | The offer is a protocol message; only C2's `accept_case_ownership_transfer` appears in the canonical ledger. |
