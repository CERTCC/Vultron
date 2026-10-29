---
title: "RVV Scenario: Reporter + Vendor1 + Vendor2"
causal_edges:
  - antecedent: validate_report
    consequent: engage_case
    consequent_actor: vendor
    note: >
      Vendor1 must validate the report before it can engage the case.
  - antecedent: engage_case
    consequent: add_participant_status_to_participant
    consequent_actor: case-actor
    note: >
      Case engagement causes the CaseActor to record participant status for
      each participant that has joined.
  - antecedent: engage_case
    consequent: invite_actor_to_case
    consequent_actor: case-actor
    note: >
      Vendor1 invites Vendor2 to the case only after the case has been engaged
      and Vendor2 has been identified as an affected party.
  - antecedent: invite_actor_to_case
    consequent: accept_invite_actor_to_case
    consequent_actor: vendor2
    note: >
      Vendor2 can only accept an invitation that has already been sent;
      the accept entry must follow the invite entry.
  - antecedent: validate_report
    consequent: close_case
    consequent_actor: vendor
    note: >
      A validated, engaged case must be present before any participant can close it.
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
      Notes are substantive protocol communications within an active case.
  - antecedent: report_submitted
    consequent: validate_report
    consequent_actor: vendor
    observable: false
    note: >
      The Reporter's initial report submission is an out-of-band API call;
      no ledger entry exists until validation occurs.
stakeholder_type: [platform-developer, project-contributor]
level: 300
page_type: reference
subject: implementation
---

# RVV Scenario: Reporter + Vendor1 + Vendor2

## Overview

The RVV scenario extends the baseline `rv` workflow to include a **second
affected Vendor** (Vendor2).  Vendor1 creates the case and directly invites
Vendor2 by sending an invitation through the protocol.  Both vendors have
independent fix paths and must each reach the fix-ready state before disclosure.

**Participants:**

- {% include-markdown "./_participant_reporter.md" trailing-newlines=false %}
- **Vendor1** — receives the report; validates, engages, and initially owns the case.
- **Vendor2** — invited by Vendor1; an additional affected party with its own fix path.
- {% include-markdown "./_participant_case_actor.md" trailing-newlines=false %}

## Protocol narrative

### 1. Reporter submits a vulnerability report to Vendor1

The Reporter identifies a vulnerability affecting products from both Vendor1 and
Vendor2 and reports it to Vendor1 as the primary contact.  This report
submission is an out-of-band event; it precedes the case's creation.

*Antecedent:* Reporter possesses knowledge of the vulnerability.

### 2. Vendor1 validates and engages the case

Vendor1 reviews the report, confirms it is credible and in scope, and engages
the case.  A `validate_report` entry and an `engage_case` entry appear in the
case ledger in that order.

*Antecedent:* Report received from Reporter (step 1).

### 3. Participant status records are created

Each record seated at case creation is ledgered as a `create_case_participant` entry, and each later status the Case Actor writes, Vendor1's engagement included, as an `add_participant_status_to_participant` entry.

*Antecedent:* `engage_case` is present in the ledger.

### 4. The Reporter asks and Vendor1 answers

The Reporter asks a question in a case note, and Vendor1 answers it.
{% include-markdown "./_case_notes.md" trailing-newlines=false %}
Vendor1 decides whom to invite only after these notes.

*Antecedent:* `engage_case` is in the ledger.

### 5. Vendor1 invites Vendor2

After confirming that Vendor2 is affected, Vendor1 sends Vendor2 an invitation
to join the case.  This is recorded as an `invite_actor_to_case` entry.

*Antecedent:* `engage_case` is present in the ledger.

### 6. Vendor2 accepts the invitation

Vendor2 receives and reviews the invitation and decides to participate.  The
acceptance is recorded as an `accept_invite_actor_to_case` entry.

*Antecedent:* `invite_actor_to_case` is present in the ledger (step 5).

### 7. Vendor2 adds a note

Vendor2, now a participant, replies in the same thread with its own status.
Its note is recorded as one more `add_note_to_case` entry.

*Antecedent:* Vendor2's `accept_invite_actor_to_case` entry is in the ledger.

### 8. Both vendors develop and ship fixes

Vendor1 and Vendor2 each advance through the fix lifecycle independently.  Both
reach fix-ready (VFd) state; participant status updates reflect progress.

*Antecedent:* `engage_case` is present in the ledger.

### 9. Vendors and Reporter publish; embargo terminates

All three participants publish.  The embargo exits ACTIVE.  The CS PXA state
advances towards publicly-known for each participant.

*Antecedent:* Both vendors have reached fix-ready status.

### 10. All participants close the case

Vendor1, Vendor2, and Reporter each close the case.
`close_case` entries appear for each.
Vendor2 and the Reporter leave first; Vendor1, the Case Owner, leaves last.
{% include-markdown "./_owner_leaves_last.md" trailing-newlines=false %}

*Antecedent:* `validate_report` and `engage_case` are in the ledger.

## Unobservable edges

| Unobservable step | Why not in ledger |
|---|---|
| Reporter submits report to Vendor1 | Report submission is an out-of-band API call that precedes the case's creation. |
