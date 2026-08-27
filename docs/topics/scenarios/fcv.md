---
title: "FCV Scenario: Finder + Coordinator + Vendor"
status: stable
causal_edges:
  - antecedent: validate_report
    consequent: engage_case
    consequent_actor: coordinator
    note: >
      The Coordinator must validate the Finder's report before engaging the case.
  - antecedent: engage_case
    consequent: add_participant_status_to_participant
    consequent_actor: case-actor
    note: >
      Case engagement causes the CaseActor to record participant status entries.
  - antecedent: engage_case
    consequent: invite_actor_to_case
    consequent_actor: coordinator
    note: >
      The Coordinator invites both the Finder and the Vendor to the case only
      after the case is active.
  - antecedent: invite_actor_to_case
    consequent: accept_invite_actor_to_case
    consequent_actor: vendor
    note: >
      A participant can only accept an invitation that has been sent; the
      accept entry follows the invite entry.
  - antecedent: validate_report
    consequent: close_case
    consequent_actor: coordinator
    note: >
      Closure requires a validated, engaged case.
  - antecedent: engage_case
    consequent: add_note_to_case
    consequent_actor: coordinator
    note: >
      Notes require an active case.
  - antecedent: report_submitted
    consequent: validate_report
    consequent_actor: coordinator
    observable: false
    note: >
      The Finder's report submission to the Coordinator is an out-of-band API
      call that precedes the case.
---

# FCV Scenario: Finder + Coordinator + Vendor

## Overview

The FCV scenario introduces a **Coordinator** who receives the initial report
from the Finder and manages participant onboarding.  The Coordinator validates
and engages the case, then invites both the Finder and the Vendor.  The Vendor
carries out the fix; the Coordinator and Finder manage communication.

**Participants:**

- **Finder** — discovers and reports the vulnerability.
- **Coordinator** — receives the report; validates, engages, and owns the case;
  invites the Finder and Vendor.
- **Vendor** — receives an invitation; develops and ships the fix.
- **CaseActor** — Coordinator's internal case-management sub-actor.

## Protocol narrative

### 1. Finder submits a vulnerability report to Coordinator

The Finder reports a vulnerability to the Coordinator's reporting endpoint.
This is an out-of-band API call; no case-ledger entry is created yet.

*Antecedent:* Finder has knowledge of the vulnerability.

### 2. Coordinator validates and engages the case

The Coordinator reviews the report and confirms it is actionable.  A
`validate_report` entry is recorded, followed by `engage_case` after the
Coordinator accepts responsibility.

*Antecedent:* Report received from Finder.

### 3. Participant status records are created

The CaseActor records the initial participant status for the Coordinator as an
`add_participant_status_to_participant` entry.

*Antecedent:* `engage_case` is in the ledger.

### 4. Coordinator invites the Finder to the case

The Coordinator sends the Finder a formal invitation.  This is recorded as an
`invite_actor_to_case` entry.

*Antecedent:* `engage_case` is in the ledger.

### 5. Finder accepts the invitation

The Finder accepts the Coordinator's invitation.  An `accept_invite_actor_to_case`
entry is recorded.

*Antecedent:* `invite_actor_to_case` is in the ledger.

### 6. Coordinator invites the Vendor

The Coordinator identifies the Vendor responsible for the affected product and
sends a second `invite_actor_to_case` entry.

*Antecedent:* `engage_case` is in the ledger.

### 7. Vendor accepts the invitation

The Vendor reviews the invitation and joins the case.  An `accept_invite_actor_to_case`
entry is recorded.

*Antecedent:* The Vendor's `invite_actor_to_case` entry is in the ledger.

### 8. Participants exchange notes

The Finder, Coordinator, and Vendor communicate through case notes.  Each
note is an `add_note_to_case` entry.

*Antecedent:* `engage_case` is in the ledger.

### 9. Vendor develops and ships a fix

The Vendor progresses through the fix lifecycle.  Participant status updates
reflect the Vendor reaching fix-ready (VFd) and fix-deployed (VFD) states.

*Antecedent:* `engage_case` is in the ledger.

### 10. Participants publish and embargo terminates

All participants publish.  The embargo exits ACTIVE.  The CS PXA state advances.

*Antecedent:* Vendor has reached fix-ready.

### 11. All participants close the case

Finder, Coordinator, and Vendor each close the case with `close_case` entries.

*Antecedent:* `validate_report` and `engage_case` are in the ledger.

## Unobservable edges

| Unobservable step | Why not in ledger |
|---|---|
| Finder submits report to Coordinator | Report submission precedes the case's creation; no ledger entry exists yet. |
