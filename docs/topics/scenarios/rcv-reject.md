---
title: "RCV-reject Scenario: Reporter + Coordinator + Vendor (Vendor Rejects)"
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
    consequent_actor: case-actor
    note: >
      The Coordinator sends the Vendor an invitation only after the case
      is active.
  - antecedent: invite_actor_to_case
    consequent: reject_invite_actor_to_case
    consequent_actor: vendor
    note: >
      The Vendor's rejection of the invitation is recorded by the CaseActor
      as a reject_invite_actor_to_case entry.  This must follow the invite.
  - antecedent: validate_report
    consequent: close_case
    consequent_actor: coordinator
    note: >
      Closure requires a validated, engaged case even when a Vendor rejected
      the invitation.
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
    consequent_actor: reporter
    note: >
      Notes require an active case.
  - antecedent: report_submitted
    consequent: validate_report
    consequent_actor: coordinator
    observable: false
    note: >
      Report submission by the Reporter is an out-of-band API call that
      precedes the case.
stakeholder_type: [platform-developer, project-contributor]
level: 300
page_type: reference
---

# RCV-reject Scenario: Reporter + Coordinator + Vendor (Vendor Rejects)

## Overview

The RCV-reject scenario follows the same initial path as RCV but diverges when
the **Vendor rejects** the Coordinator's invitation.  The Vendor declines
participation; the case continues with only the Reporter and the Coordinator,
who eventually disclose and close the case without the Vendor's involvement.

This scenario validates the rejection path of the invite protocol (CLP-13).

**Participants:**

- **Reporter** — discovers the vulnerability and submits the report; in the case it holds the Reporter role; the protocol has no separate Finder role ([ADR-0078](../../adr/0078-retire-finder-role.md)).
- **Coordinator** — receives the report; validates, engages, and owns the case.
- **Vendor** — receives an invitation; **rejects** it and does not join.
- **Case Actor** — the actor that holds the [CASE_MANAGER](../case_lifecycle/case_manager_and_ledger.md) role for this case; it writes every canonical ledger entry and fans it out to the participants. In the demo it runs on the dedicated `case-actor` container, but its authority comes from the role, not from where it runs.

## Protocol narrative

### 1. Reporter submits a vulnerability report to Coordinator

The Reporter reports to the Coordinator's endpoint.  This is an out-of-band
API call with no corresponding ledger entry.

*Antecedent:* Reporter has knowledge of the vulnerability.

### 2. Coordinator validates and engages the case

The Coordinator reviews the report and accepts it.  `validate_report` then
`engage_case` entries appear in the case ledger.

*Antecedent:* Report received from Reporter.

### 3. Participant status records are created

Each record seated at case creation is ledgered as a `create_case_participant` entry, and each later status the Case Actor writes, the engagement included, as an `add_participant_status_to_participant` entry.
The Reporter is one of them: it joins the case as a signatory when the case is created, so the Coordinator never invites it.

*Antecedent:* `engage_case` is in the ledger.

### 4. Coordinator invites the Vendor

The Coordinator identifies the Vendor and asks the Case Actor to invite it.
The Case Actor sends the Invite and records it as an `invite_actor_to_case` entry, the only one in this scenario.

*Antecedent:* `engage_case` is in the ledger.

### 5. Vendor rejects the invitation

The Vendor declines to participate.  The Case Actor records the Vendor's `Reject` as a
`reject_invite_actor_to_case` entry.  **The Vendor is not added as a participant.**

*Antecedent:* The Vendor's `invite_actor_to_case` entry is in the ledger.

### 6. Reporter and Coordinator exchange notes

Reporter and Coordinator communicate through case notes.
Each note is sent as one `Add(Note)` carrying the note inline, and recorded as an `add_note_to_case` entry, which attaches it to the case.

*Antecedent:* `engage_case` is in the ledger.

### 7. Participants publish; embargo terminates

The Coordinator and Reporter publish.  The embargo exits ACTIVE without the
Vendor's participation.

*Antecedent:* `engage_case` is in the ledger.

### 8. Reporter and Coordinator close the case

Reporter and Coordinator each submit `close_case` entries.
The Reporter leaves first; the Coordinator, the Case Owner, leaves last.
A departure sent after the owner's is not recorded, so every other participant's departure is recorded first.
The Vendor, having rejected the invitation, has no close entry.

*Antecedent:* `validate_report` and `engage_case` are in the ledger.

## Unobservable edges

| Unobservable step | Why not in ledger |
|---|---|
| Reporter submits report to Coordinator | Report submission precedes the case. |
