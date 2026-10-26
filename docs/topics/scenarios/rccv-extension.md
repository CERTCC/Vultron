---
title: "RCCV-extension Scenario: Reporter + C1 + C2 + Vendor"
# consequent_actor names the dump actor recorded on the consequent entry:
# C1 is 'vendor', C2 is 'coordinator', the Vendor is 'vendor2'.
causal_edges:
  - antecedent: validate_report
    consequent: engage_case
    consequent_actor: vendor
    note: >
      C1 validates the report before engaging the case.
  - antecedent: engage_case
    consequent: add_participant_status_to_participant
    consequent_actor: case-actor
    note: >
      Case engagement triggers participant status entries.
  - antecedent: engage_case
    consequent: invite_actor_to_case
    consequent_actor: case-actor
    note: >
      C1 invites C2 after the case is active.
  - antecedent: invite_actor_to_case
    consequent: accept_invite_actor_to_case
    consequent_actor: coordinator
    note: >
      C2 accepts C1's invitation; acceptance follows the invite.
  - antecedent: accept_invite_actor_to_case
    consequent: offer_case_participant
    consequent_actor: case-actor
    note: >
      C2, having joined, suggests the Vendor via the actor-suggestion flow
      (ADR-0026).  The offer requires C2 to already be a participant.
  - antecedent: offer_case_participant
    consequent: accept_actor_recommendation
    consequent_actor: case-actor
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
    consequent_actor: vendor2
    note: >
      The Vendor accepts the CaseActor's invitation.  Because both this
      accept and C2's earlier accept share the same semantic type, the ordering
      check verifies that the earliest accept_invite precedes the latest
      invite; the valid pair is C2's accept → CaseActor's invite to Vendor.
  - antecedent: validate_report
    consequent: close_case
    consequent_actor: vendor
    note: >
      Closure requires a validated, engaged case.
  - antecedent: close_case
    consequent: close_case
    consequent_actor: vendor
    note: >
      C1, the Case Owner, leaves last (CM-23-015): another
      participant's close_case precedes the owner's.  The owner's departure
      closes the case, and a departure sent after it is not recorded
      (CM-23-013).
  - antecedent: engage_case
    consequent: add_note_to_case
    consequent_actor: reporter
    note: >
      Notes require an active case.
  - antecedent: report_submitted
    consequent: validate_report
    consequent_actor: vendor
    observable: false
    note: >
      Report submission by the Reporter is an out-of-band API call that
      precedes the case.
stakeholder_type: [platform-developer, project-contributor]
level: 300
page_type: reference
---

# RCCV-extension Scenario: Reporter + C1 + C2 + Vendor

## Overview

The RCCV-extension scenario exercises a **two-coordinator case** where the
second coordinator (C2) acts as a broker for the Vendor via the actor-suggestion
flow.  The Reporter reports to C1 (the initial coordinator and case owner).  C1
invites C2; C2 then suggests the Vendor to the case.  C1 approves the suggestion
and the Case Actor formally invites the Vendor.

**Participants:**

{% include-markdown "./_participant_reporter.md" trailing-newlines=false %}

- **C1 (Coordinator 1)** — receives the report; validates, engages, and owns the case; invites C2.
- **C2 (Coordinator 2)** — joins via C1's invitation; suggests the Vendor.
- **Vendor** — joins via the actor-suggestion path; develops and ships a fix.
{% include-markdown "./_participant_case_actor.md" trailing-newlines=false %}

## Protocol narrative

### 1. Reporter submits a vulnerability report to C1

The Reporter reports to C1's endpoint.  No ledger entry is created yet.

*Antecedent:* Reporter has knowledge of the vulnerability.

### 2. C1 validates and engages the case

C1 reviews the report and accepts it.  `validate_report` and `engage_case`
entries appear in the ledger.

*Antecedent:* Report received from Reporter.

### 3. Participant status records are created

{% include-markdown "./_engagement_status_entry.md" %}

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

### 8. Case Actor invites the Vendor

The Case Actor sends the Vendor an `invite_actor_to_case` entry.

*Antecedent:* `accept_actor_recommendation` is in the ledger.

### 9. Vendor accepts the invitation

The Vendor joins the case.  An `accept_invite_actor_to_case` entry is recorded.

*Antecedent:* The Case Actor's `invite_actor_to_case` entry is in the ledger.

### 10. Participants exchange notes

{% include-markdown "./_case_notes.md" %}

*Antecedent:* `engage_case` is in the ledger.

### 11. Vendor reaches fix-ready

The Vendor advances to VFd (fix-ready) status.

*Antecedent:* `engage_case` is in the ledger.

### 12. Participants publish; embargo terminates

All participants publish.  The embargo exits ACTIVE.

*Antecedent:* Vendor has reached fix-ready.

### 13. All participants close the case

`close_case` entries appear for each participant.
The Vendor, C2, and the Reporter leave first; C1, the Case Owner, leaves last.
{% include-markdown "./_owner_leaves_last.md" trailing-newlines=false %}

*Antecedent:* `validate_report` and `engage_case` are in the ledger.

## Unobservable edges

| Unobservable step | Why not in ledger |
|---|---|
| Reporter submits report to C1 | Report submission precedes the case. |
