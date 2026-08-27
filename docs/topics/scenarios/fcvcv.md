---
title: "FCVCV Scenario: Finder + C1 + V1 + C2 + V2"
status: stable
causal_edges:
  - antecedent: validate_report
    consequent: engage_case
    consequent_actor: c1
    note: >
      C1 (the initial case owner) validates the report before engaging the case.
  - antecedent: engage_case
    consequent: add_participant_status_to_participant
    consequent_actor: case-actor
    note: >
      Case engagement triggers participant status entries.
  - antecedent: engage_case
    consequent: invite_actor_to_case
    consequent_actor: c1
    note: >
      C1 invites both V1 and C2 after the case is active.
  - antecedent: invite_actor_to_case
    consequent: accept_invite_actor_to_case
    consequent_actor: v1
    note: >
      V1 and C2 each accept C1's invitation; acceptances follow the invites.
  - antecedent: accept_invite_actor_to_case
    consequent: offer_case_participant
    consequent_actor: c2
    note: >
      After C2 joins, C2 suggests V2 to the case via the actor-suggestion flow
      (ADR-0026).  The offer can only be made by a participant, so C2's
      acceptance must precede the offer.
  - antecedent: offer_case_participant
    consequent: accept_actor_recommendation
    consequent_actor: c1
    note: >
      C1, as case owner, approves C2's suggestion.  The recommendation
      acceptance follows the offer.
  - antecedent: accept_actor_recommendation
    consequent: invite_actor_to_case
    consequent_actor: case-actor
    note: >
      After C1 approves, the CaseActor sends V2 a formal invitation
      (ADR-0026 path).  This invite follows the recommendation acceptance.
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

# FCVCV Scenario: Finder + C1 + V1 + C2 + V2

## Overview

The FCVCV scenario exercises the **actor-suggestion flow** (ADR-0026).  A
Finder reports to Coordinator 1 (C1), who creates the case and directly invites
Vendor 1 (V1) and Coordinator 2 (C2).  After C2 joins, C2 *suggests* Vendor 2
(V2) to the case; C1, as the case owner, approves the recommendation and the
CaseActor sends V2 a formal invitation.

This five-actor scenario validates the indirect participant onboarding path
where C2 acts as a broker for V2 rather than C1 inviting V2 directly.

**Participants:**

- **Finder** — discovers the vulnerability; submits the initial report.
- **C1 (Coordinator 1)** — receives the report; validates, engages, and owns the case; invites V1 and C2.
- **V1 (Vendor 1)** — receives a direct invite from C1; develops a fix (reaches VFd, not VFD).
- **C2 (Coordinator 2)** — receives a direct invite from C1; suggests V2 to the case.
- **V2 (Vendor 2 / Deployer)** — joins via the actor-suggestion path; develops and deploys a fix (VFD).
- **CaseActor** — C1's internal case-management sub-actor.

## Protocol narrative

### 1. Finder submits a vulnerability report to C1

The Finder reports to C1's endpoint.  This is an out-of-band API call; no
ledger entry is created.

*Antecedent:* Finder has knowledge of the vulnerability.

### 2. C1 validates and engages the case

C1 reviews the report and accepts it.  `validate_report` and `engage_case`
entries appear in the ledger.

*Antecedent:* Report received from Finder.

### 3. Participant status records are created

The CaseActor records initial participant status entries.

*Antecedent:* `engage_case` is in the ledger.

### 4. C1 invites V1 and C2

C1 sends `invite_actor_to_case` entries to both V1 and C2.

*Antecedent:* `engage_case` is in the ledger.

### 5. V1 and C2 accept their invitations

Each invitee accepts.  Two `accept_invite_actor_to_case` entries appear.

*Antecedent:* Their respective `invite_actor_to_case` entries are in the ledger.

### 6. C2 suggests V2 via the actor-suggestion flow

C2 is aware that V2 is also affected.  C2 submits an `offer_case_participant`
entry proposing V2 for case membership (ADR-0026).

*Antecedent:* C2's `accept_invite_actor_to_case` entry is in the ledger.

### 7. C1 approves C2's recommendation

C1, as case owner, reviews the suggestion and approves it.  An
`accept_actor_recommendation` entry is recorded.

*Antecedent:* `offer_case_participant` is in the ledger.

### 8. CaseActor sends V2 a formal invitation

The CaseActor, acting on C1's approval, sends V2 an `invite_actor_to_case`
entry.  This follows the ADR-0026 suggest-actor path.

*Antecedent:* `accept_actor_recommendation` is in the ledger.

### 9. V2 accepts the CaseActor invitation

V2 reviews and accepts the invitation.  An `accept_invite_actor_to_case` entry
is recorded for V2.

*Antecedent:* The CaseActor's `invite_actor_to_case` entry is in the ledger.

### 10. Participants exchange notes

All participants communicate through `add_note_to_case` entries.

*Antecedent:* `engage_case` is in the ledger.

### 11. V1 reaches fix-ready; V2 reaches fix-deployed

V1 advances to VFd (fix-ready) but stops there.  V2 advances all the way to
VFD (fix-deployed).  Participant status updates reflect each state change.

*Antecedent:* `engage_case` is in the ledger.

### 12. Participants publish; embargo terminates

All participants publish.  The embargo exits ACTIVE.

*Antecedent:* At least one vendor has reached fix-ready.

### 13. All participants close the case

All five participants close the case.  `close_case` entries appear for each.

*Antecedent:* `validate_report` and `engage_case` are in the ledger.

## Unobservable edges

| Unobservable step | Why not in ledger |
|---|---|
| Finder submits report to C1 | Report submission precedes the case. |
