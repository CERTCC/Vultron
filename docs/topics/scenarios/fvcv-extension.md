---
title: "FVCV-extension Scenario: Finder + Vendor1 + Coordinator + Vendor2"
status: stable
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
    consequent_actor: vendor
    note: >
      Vendor1 invites the Coordinator to the case after engagement.
  - antecedent: invite_actor_to_case
    consequent: accept_invite_actor_to_case
    consequent_actor: coordinator
    note: >
      The Coordinator accepts Vendor1's invitation; acceptance follows the invite.
  - antecedent: accept_invite_actor_to_case
    consequent: offer_case_participant
    consequent_actor: coordinator
    note: >
      After joining, the Coordinator suggests Vendor2 via the actor-suggestion
      flow (ADR-0026).  The offer can only be submitted by a participant, so the
      Coordinator's acceptance must precede it.
  - antecedent: offer_case_participant
    consequent: accept_actor_recommendation
    consequent_actor: vendor
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
  - antecedent: engage_case
    consequent: add_note_to_case
    consequent_actor: finder
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

# FVCV-extension Scenario: Finder + Vendor1 + Coordinator + Vendor2

## Overview

The FVCV-extension scenario shows a **Vendor-initiated case** that grows through
a Coordinator to include a second Vendor via the actor-suggestion flow.  The
Finder reports to Vendor1, who owns and coordinates the case.  Vendor1 invites a
Coordinator; the Coordinator then suggests Vendor2 to the case.  Vendor1, as
case owner, approves the suggestion, and the CaseActor formally invites Vendor2.

Both vendors reach the fix-ready state before joint disclosure.

**Participants:**

- **Finder** — discovers the vulnerability; submits the initial report.
- **Vendor1** — receives the report; validates, engages, and owns the case.
- **Coordinator** — invited by Vendor1; suggests Vendor2.
- **Vendor2** — joins via the actor-suggestion path; develops and ships a fix.
- **CaseActor** — Vendor1's internal case-management sub-actor.

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

### 6. Coordinator suggests Vendor2

The Coordinator recognises that Vendor2 is affected and submits an
`offer_case_participant` entry proposing Vendor2 for membership (ADR-0026).

*Antecedent:* Coordinator's `accept_invite_actor_to_case` entry is in the ledger.

### 7. Vendor1 approves the recommendation

Vendor1, as case owner, reviews and approves the suggestion.  An
`accept_actor_recommendation` entry is recorded.

*Antecedent:* `offer_case_participant` is in the ledger.

### 8. CaseActor invites Vendor2

The CaseActor, acting on Vendor1's approval, sends Vendor2 an
`invite_actor_to_case` entry.

*Antecedent:* `accept_actor_recommendation` is in the ledger.

### 9. Vendor2 accepts the invitation

Vendor2 reviews and accepts.  An `accept_invite_actor_to_case` entry is recorded.

*Antecedent:* The CaseActor's `invite_actor_to_case` entry is in the ledger.

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

*Antecedent:* `validate_report` and `engage_case` are in the ledger.

## Unobservable edges

| Unobservable step | Why not in ledger |
|---|---|
| Finder submits report to Vendor1 | Report submission precedes the case. |
