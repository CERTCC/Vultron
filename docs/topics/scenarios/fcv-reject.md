---
title: "FCV-reject Scenario: Finder + Coordinator + Vendor (Vendor Rejects)"
status: stable
causal_edges:
  - antecedent: validate_report
    consequent: engage_case
    consequent_actor: coordinator
    note: >
      The Coordinator validates and then engages the case before inviting
      the Vendor.
  - antecedent: engage_case
    consequent: add_participant_status_to_participant
    consequent_actor: case-actor
    note: >
      Participant status records are created after case engagement.
  - antecedent: engage_case
    consequent: invite_actor_to_case
    consequent_actor: coordinator
    note: >
      The Coordinator sends the Vendor an invitation only after the case
      is active.
  - antecedent: invite_actor_to_case
    consequent: reject_invite_actor_to_case
    consequent_actor: coordinator
    note: >
      The Vendor's rejection of the invitation is recorded by the CaseActor
      as a reject_invite_actor_to_case entry.  This must follow the invite.
  - antecedent: validate_report
    consequent: close_case
    consequent_actor: coordinator
    note: >
      Closure requires a validated, engaged case even when a Vendor rejected
      the invitation.
  - antecedent: engage_case
    consequent: add_note_to_case
    consequent_actor: finder
    note: >
      Notes require an active case.
  - antecedent: report_submitted
    consequent: validate_report
    consequent_actor: coordinator
    observable: false
    note: >
      Report submission by the Finder is an out-of-band API call that
      precedes the case.
---

# FCV-reject Scenario: Finder + Coordinator + Vendor (Vendor Rejects)

## Overview

The FCV-reject scenario follows the same initial path as FCV but diverges when
the **Vendor rejects** the Coordinator's invitation.  The Vendor declines
participation; the case continues with only the Finder and the Coordinator,
who eventually disclose and close the case without the Vendor's involvement.

This scenario validates the rejection path of the invite protocol (CLP-13).

**Participants:**

- **Finder** — discovers and reports the vulnerability.
- **Coordinator** — receives the report; validates, engages, and owns the case.
- **Vendor** — receives an invitation; **rejects** it and does not join.
- **CaseActor** — Coordinator's internal case-management sub-actor.

## Protocol narrative

### 1. Finder submits a vulnerability report to Coordinator

The Finder reports to the Coordinator's endpoint.  This is an out-of-band
API call with no corresponding ledger entry.

*Antecedent:* Finder has knowledge of the vulnerability.

### 2. Coordinator validates and engages the case

The Coordinator reviews the report and accepts it.  `validate_report` then
`engage_case` entries appear in the case ledger.

*Antecedent:* Report received from Finder.

### 3. Participant status records are created

The CaseActor records `add_participant_status_to_participant` for each initial
participant.

*Antecedent:* `engage_case` is in the ledger.

### 4. Coordinator invites the Finder

The Coordinator sends the Finder a formal `invite_actor_to_case` entry.

*Antecedent:* `engage_case` is in the ledger.

### 5. Finder accepts the invitation

The Finder accepts.  An `accept_invite_actor_to_case` entry is recorded.

*Antecedent:* The Finder's `invite_actor_to_case` entry is in the ledger.

### 6. Coordinator invites the Vendor

The Coordinator identifies the Vendor and sends an `invite_actor_to_case` entry.

*Antecedent:* `engage_case` is in the ledger.

### 7. Vendor rejects the invitation

The Vendor declines to participate.  The CaseActor records the rejection as a
`reject_invite_actor_to_case` entry.  **The Vendor is not added as a participant.**

*Antecedent:* The Vendor's `invite_actor_to_case` entry is in the ledger.

### 8. Finder and Coordinator exchange notes

Finder and Coordinator communicate through case notes (`add_note_to_case`).

*Antecedent:* `engage_case` is in the ledger.

### 9. Participants publish; embargo terminates

The Coordinator and Finder publish.  The embargo exits ACTIVE without the
Vendor's participation.

*Antecedent:* `engage_case` is in the ledger.

### 10. Finder and Coordinator close the case

Finder and Coordinator each submit `close_case` entries.  The Vendor, having
rejected the invitation, has no close entry.

*Antecedent:* `validate_report` and `engage_case` are in the ledger.

## Unobservable edges

| Unobservable step | Why not in ledger |
|---|---|
| Finder submits report to Coordinator | Report submission precedes the case. |
