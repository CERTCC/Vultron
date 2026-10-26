---
title: "RCV Scenario: Reporter + Coordinator + Vendor"
causal_edges:
  - antecedent: validate_report
    consequent: engage_case
    consequent_actor: coordinator
    note: >
      The Coordinator must validate the Reporter's report before engaging the case.
  - antecedent: engage_case
    consequent: add_participant_status_to_participant
    consequent_actor: case-actor
    note: >
      Case engagement causes the CaseActor to record participant status entries.
  - antecedent: engage_case
    consequent: invite_actor_to_case
    consequent_actor: case-actor
    note: >
      The Coordinator invites the Vendor to the case only after the case is
      active.  The Reporter is seated at case creation and is not
      invited.
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
    consequent_actor: coordinator
    note: >
      Notes require an active case.
  - antecedent: report_submitted
    consequent: validate_report
    consequent_actor: coordinator
    observable: false
    note: >
      The Reporter's report submission to the Coordinator is an out-of-band API
      call that precedes the case.
stakeholder_type: [platform-developer, project-contributor]
level: 300
page_type: reference
---

# RCV Scenario: Reporter + Coordinator + Vendor

## Overview

The RCV scenario introduces a **Coordinator** who receives the initial report from the Reporter and manages participant onboarding.
The Coordinator validates and engages the case, then invites the Vendor.
The Reporter is a participant from the moment the case is created, so it receives no invitation.
The Vendor carries out the fix; the Coordinator and Reporter manage communication.

**Participants:**

- {% include-markdown "./_participant_reporter.md" trailing-newlines=false %}
- **Coordinator** — receives the report; validates, engages, and owns the case;
  invites the Vendor.
- **Vendor** — receives an invitation; develops and ships the fix.
- {% include-markdown "./_participant_case_actor.md" trailing-newlines=false %}

## Protocol narrative

### 1. Reporter submits a vulnerability report to Coordinator

The Reporter reports a vulnerability to the Coordinator's reporting endpoint.
This is an out-of-band API call; no case-ledger entry is created yet.

*Antecedent:* Reporter has knowledge of the vulnerability.

### 2. Coordinator validates and engages the case

The Coordinator reviews the report and confirms it is actionable.  A
`validate_report` entry is recorded, followed by `engage_case` after the
Coordinator accepts responsibility.

*Antecedent:* Report received from Reporter.

### 3. Participant status records are created

Each record seated at case creation is ledgered as a `create_case_participant` entry, and each later status the Case Actor writes, the Vendor's engagement included, as an `add_participant_status_to_participant` entry.
The Reporter is one of them: it joins the case as a signatory when the case is created, so the Coordinator never invites it.

*Antecedent:* `engage_case` is in the ledger.

### 4. Coordinator invites the Vendor

The Coordinator identifies the Vendor responsible for the affected product and asks the Case Actor to invite it.
The Case Actor sends the Invite and records it as an `invite_actor_to_case` entry, the only one in this scenario.

*Antecedent:* `engage_case` is in the ledger.

### 5. Vendor accepts the invitation

The Vendor reviews the invitation and joins the case.
An `accept_invite_actor_to_case` entry is recorded.

*Antecedent:* The Vendor's `invite_actor_to_case` entry is in the ledger.

### 6. Participants exchange notes

The Reporter, Coordinator, and Vendor communicate through case notes.
{% include-markdown "./_case_notes.md" trailing-newlines=false %}

*Antecedent:* `engage_case` is in the ledger.

### 7. Vendor develops and ships a fix

The Vendor progresses through the fix lifecycle.
Participant status updates reflect the Vendor reaching the fix-ready (VFd) state.
No participant deploys a fix in this scenario, so the VFD state stays at VFd.

*Antecedent:* `engage_case` is in the ledger.

### 8. Participants publish and embargo terminates

All participants publish.  The embargo exits ACTIVE.  The CS PXA state advances.

*Antecedent:* Vendor has reached fix-ready.

### 9. All participants close the case

Reporter, Coordinator, and Vendor each close the case with `close_case` entries.
The Vendor and the Reporter leave first; the Coordinator, the Case Owner, leaves last.
{% include-markdown "./_owner_leaves_last.md" trailing-newlines=false %}

*Antecedent:* `validate_report` and `engage_case` are in the ledger.

## Unobservable edges

| Unobservable step | Why not in ledger |
|---|---|
| Reporter submits report to Coordinator | Report submission precedes the case's creation; no ledger entry exists yet. |
