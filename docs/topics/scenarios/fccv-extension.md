---
title: "FCCV-extension Scenario: Finder + C1 + C2 + Vendor"
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
    consequent: offer_case_participant
    consequent_actor: c2
    note: >
      C2, having joined, suggests the Vendor via the actor-suggestion flow
      (ADR-0026).  The offer requires C2 to already be a participant.
  - antecedent: offer_case_participant
    consequent: accept_actor_recommendation
    consequent_actor: c1
    note: >
      C1, as case owner, approves C2's suggestion.
  - antecedent: accept_actor_recommendation
    consequent: invite_actor_to_case
    consequent_actor: case-actor
    note: >
      The CaseActor sends the Vendor a formal invitation after C1 approves
      (ADR-0026 path).
  - antecedent: invite_actor_to_case
    consequent: accept_invite_actor_to_case
    consequent_actor: vendor
    note: >
      The Vendor accepts the CaseActor's invitation.  Because both this
      accept and C2's earlier accept share the same event type, the ordering
      check verifies that the earliest accept_invite precedes the latest
      invite; the valid pair is C2's accept → CaseActor's invite to Vendor.
  - antecedent: validate_report
    consequent: close_case
    consequent_actor: c1
    note: >
      Closure requires a validated, engaged case.
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

# FCCV-extension Scenario: Finder + C1 + C2 + Vendor

## Overview

The FCCV-extension scenario exercises a **two-coordinator case** where the
second coordinator (C2) acts as a broker for the Vendor via the actor-suggestion
flow.  The Finder reports to C1 (the initial coordinator and case owner).  C1
invites C2; C2 then suggests the Vendor to the case.  C1 approves the suggestion
and the CaseActor formally invites the Vendor.

**Participants:**

- **Finder** — discovers the vulnerability; submits the initial report.
- **C1 (Coordinator 1)** — receives the report; validates, engages, and owns the case; invites C2.
- **C2 (Coordinator 2)** — joins via C1's invitation; suggests the Vendor.
- **Vendor** — joins via the actor-suggestion path; develops and ships a fix.
- **CaseActor** — C1's internal case-management sub-actor.

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

### 6. C2 suggests the Vendor

C2 identifies the Vendor as an affected party and submits an
`offer_case_participant` entry proposing the Vendor for membership (ADR-0026).

*Antecedent:* C2's `accept_invite_actor_to_case` entry is in the ledger.

### 7. C1 approves the recommendation

C1, as case owner, reviews and approves the suggestion.  An
`accept_actor_recommendation` entry is recorded.

*Antecedent:* `offer_case_participant` is in the ledger.

### 8. CaseActor invites the Vendor

The CaseActor sends the Vendor an `invite_actor_to_case` entry.

*Antecedent:* `accept_actor_recommendation` is in the ledger.

### 9. Vendor accepts the invitation

The Vendor joins the case.  An `accept_invite_actor_to_case` entry is recorded.

*Antecedent:* The CaseActor's `invite_actor_to_case` entry is in the ledger.

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

`close_case` entries appear for each participant.

*Antecedent:* `validate_report` and `engage_case` are in the ledger.

## Unobservable edges

| Unobservable step | Why not in ledger |
|---|---|
| Finder submits report to C1 | Report submission precedes the case. |
