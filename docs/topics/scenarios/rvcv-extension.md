---
title: "RVCV-extension Scenario: Reporter + Vendor1 + Coordinator + Vendor2"
causal_edges:
  - antecedent: validate_report
    consequent: engage_case
    consequent_actor: vendor
    note: >
      Vendor1 validates the report before engaging the case.
  - antecedent: engage_case
    consequent: add_participant_status_to_participant
    consequent_actor: case-actor
    note: >
      Case engagement triggers participant status entries.
  - antecedent: engage_case
    consequent: invite_actor_to_case
    consequent_actor: case-actor
    note: >
      Vendor1 invites the Coordinator to the case after engagement.
  - antecedent: invite_actor_to_case
    consequent: accept_invite_actor_to_case
    consequent_actor: coordinator
    note: >
      The Coordinator accepts Vendor1's invitation; acceptance follows the invite.
  - antecedent: accept_invite_actor_to_case
    consequent: offer_case_participant
    consequent_actor: case-actor
    note: >
      After joining, the Coordinator suggests Vendor2 via the actor-suggestion
      flow (ADR-0026).  The offer can only be submitted by a participant, so the
      Coordinator's acceptance must precede it.
  - antecedent: offer_case_participant
    consequent: accept_actor_recommendation
    consequent_actor: case-actor
    note: >
      Vendor1, as case owner, approves the Coordinator's suggestion.
  - antecedent: accept_actor_recommendation
    consequent: invite_actor_to_case
    consequent_actor: case-actor
    note: >
      The CaseActor sends Vendor2 a formal invitation after the recommendation
      is approved (ADR-0026 path).
  - antecedent: invite_actor_to_case
    consequent: accept_invite_actor_to_case
    consequent_actor: vendor2
    note: >
      Vendor2 accepts the CaseActor's invitation; acceptance follows the invite.
  - antecedent: validate_report
    consequent: close_case
    consequent_actor: vendor
    note: >
      Closure requires a validated, engaged case.
  - antecedent: close_case
    consequent: close_case
    consequent_actor: vendor
    note: >
      Vendor1, the Case Owner, leaves last (CM-23-015): another
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

# RVCV-extension Scenario: Reporter + Vendor1 + Coordinator + Vendor2

## Overview

The RVCV-extension scenario shows a **Vendor-initiated case** that grows through
a Coordinator to include a second Vendor via the actor-suggestion flow.  The
Reporter reports to Vendor1, who owns and coordinates the case.  Vendor1 invites a
Coordinator; the Coordinator then suggests Vendor2 to the case.  Vendor1, as
case owner, approves the suggestion, and the Case Actor formally invites Vendor2.

Both vendors reach the fix-ready state before joint disclosure.

**Participants:**

{% include-markdown "./_participant_reporter.md" trailing-newlines=false %}

- **Vendor1** — receives the report; validates, engages, and owns the case.
- **Coordinator** — invited by Vendor1; suggests Vendor2.
- **Vendor2** — joins via the actor-suggestion path; develops and ships a fix.
{% include-markdown "./_participant_case_actor.md" trailing-newlines=false %}

## Protocol narrative

### 1. Reporter submits a vulnerability report to Vendor1

The Reporter reports to Vendor1's endpoint.  No ledger entry is created yet.

*Antecedent:* Reporter has knowledge of the vulnerability.

### 2. Vendor1 validates and engages the case

Vendor1 reviews the report and accepts it.  `validate_report` and `engage_case`
entries appear in the ledger.

*Antecedent:* Report received from Reporter.

### 3. Participant status records are created

{% include-markdown "./_engagement_status_entry.md" %}

*Antecedent:* `engage_case` is in the ledger.

### 4. Vendor1 invites the Coordinator

Vendor1 sends the Coordinator an `invite_actor_to_case` entry.

*Antecedent:* `engage_case` is in the ledger.

### 5. Coordinator accepts the invitation

The Coordinator joins the case.  An `accept_invite_actor_to_case` entry is
recorded.

*Antecedent:* `invite_actor_to_case` is in the ledger (step 4).

### 6. Coordinator suggests Vendor2

The Coordinator recognizes that Vendor2 is affected and submits an
`offer_case_participant` entry proposing Vendor2 for membership (ADR-0026).

*Antecedent:* Coordinator's `accept_invite_actor_to_case` entry is in the ledger.

### 7. Vendor1 approves the recommendation

Vendor1, as case owner, reviews and approves the suggestion.  An
`accept_actor_recommendation` entry is recorded.

*Antecedent:* `offer_case_participant` is in the ledger.

### 8. Case Actor invites Vendor2

The Case Actor, acting on Vendor1's approval, sends Vendor2 an
`invite_actor_to_case` entry.

*Antecedent:* `accept_actor_recommendation` is in the ledger.

### 9. Vendor2 accepts the invitation

Vendor2 reviews and accepts.  An `accept_invite_actor_to_case` entry is recorded.

*Antecedent:* The Case Actor's `invite_actor_to_case` entry is in the ledger.

### 10. Participants exchange notes

{% include-markdown "./_case_notes.md" %}

*Antecedent:* `engage_case` is in the ledger.

### 11. Both vendors reach fix-ready

Vendor1 and Vendor2 each advance to VFd (fix-ready) status.

*Antecedent:* `engage_case` is in the ledger.

### 12. Participants publish; embargo terminates

All participants publish.  The embargo exits ACTIVE.

*Antecedent:* At least one vendor has reached fix-ready.

### 13. All participants close the case

`close_case` entries appear for each participant.
Vendor2, the Coordinator, and the Reporter leave first; Vendor1, the Case Owner, leaves last.
{% include-markdown "./_owner_leaves_last.md" trailing-newlines=false %}

*Antecedent:* `validate_report` and `engage_case` are in the ledger.

## Unobservable edges

| Unobservable step | Why not in ledger |
|---|---|
| Reporter submits report to Vendor1 | Report submission precedes the case. |
