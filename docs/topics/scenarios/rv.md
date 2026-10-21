---
title: "rv Scenario: Reporter + Vendor"
causal_edges:
  - antecedent: validate_report
    consequent: engage_case
    consequent_actor: vendor
    note: >
      The vendor cannot engage the case until the report has been validated.
      Validation confirms the report is credible and in scope.
  - antecedent: engage_case
    consequent: add_participant_status_to_participant
    consequent_actor: case-actor
    note: >
      The Case Actor records each engagement's RM ACCEPTED as a participant
      status entry right after the engage_case entry, carrying the status it
      stored (CLP-07-013).
  - antecedent: validate_report
    consequent: close_case
    consequent_actor: vendor
    note: >
      The case must have been validated before it can be closed; a case that
      was never validated is not a real coordinated-disclosure lifecycle.
  - antecedent: close_case
    consequent: close_case
    consequent_actor: vendor
    note: >
      The Vendor, the Case Owner, leaves last (CM-23-015): another
      participant's close_case precedes the owner's.  The owner's departure
      closes the case, and a departure sent after it is not recorded
      (CM-23-013).
  - antecedent: engage_case
    consequent: add_note_to_case
    consequent_actor: reporter
    note: >
      Protocol notes are substantive communications within an active case;
      they cannot precede case engagement.
  - antecedent: report_submitted
    consequent: validate_report
    consequent_actor: vendor
    observable: false
    note: >
      The reporter's act of submitting a report to the vendor's API is not
      itself recorded as a case-ledger entry; it is an out-of-band event that
      precedes the case's existence.  The first observable ledger entry for
      this causal chain is validate_report.
stakeholder_type: [platform-developer, project-contributor]
level: 300
page_type: reference
---

# `rv` Scenario: Reporter + Vendor

## Overview

The `rv` scenario is the baseline two-actor Coordinated Vulnerability Disclosure
workflow.  A **Reporter** discovers a vulnerability and submits a report to the
affected **Vendor**.  The Vendor validates and engages the case, develops a
fix, publishes an advisory, and closes the case.  The Reporter and Vendor work
directly with no coordinator.

**Participants:**

- **Reporter** — discovers the vulnerability and submits the report; in the case it holds the Reporter role; the protocol has no separate Finder role ([ADR-0078](../../adr/0078-retire-finder-role.md)).
- **Vendor** — receives the report; validates, engages, and owns the case.
- **Case Actor** — the actor that holds the [CASE_MANAGER](../case_lifecycle/case_manager_and_ledger.md) role for this case; it writes every canonical ledger entry and fans it out to the participants. In the demo it runs on the dedicated `case-actor` container, but its authority comes from the role, not from where it runs.

## Protocol narrative

### 1. Reporter submits a vulnerability report to Vendor

The Reporter becomes aware of a security vulnerability in a Vendor product and
initiates disclosure.  The Reporter sends a report to the Vendor's reporting
endpoint.  This act is not directly recorded in the case ledger; it is the
trigger that causes the case to be created on the Vendor's side.

*Antecedent:* Reporter possesses knowledge of the vulnerability and a channel to
the Vendor.

### 2. Vendor validates the report

The Vendor receives the report and evaluates whether it describes a credible,
in-scope vulnerability.  A successful validation advances the Vendor's RM state
from RECEIVED to VALID and records a `validate_report` entry in the case ledger.

*Antecedent:* Vendor received the report (step 1).

### 3. Vendor engages the case

The Vendor decides to act on the validated report and formally accepts
responsibility for coordinating the response.  This advances the Vendor's RM
state to ACCEPTED and records an `engage_case` entry in the ledger.

*Antecedent:* `validate_report` is present in the ledger.

### 4. Participant status records are created

When the Case Actor records an engagement, it commits the RM status it wrote for the engaging actor as an `add_participant_status_to_participant` entry right after the `engage_case` entry ([CLP-07-013](../../reference/specs/protocol.md#clp-07-013)).
Every replica copies that status, its id and time included.
The records seated at case creation were ledgered earlier, each as a `create_case_participant` entry.

*Antecedent:* `engage_case` is present in the ledger.

### 5. Reporter and Vendor exchange notes

Participants communicate about the vulnerability through case notes.
Each note is posted via the protocol as one `Add(Note)` carrying the note inline.
The ledger records it as an `add_note_to_case` entry, which attaches it to the case.
The Reporter may ask about workarounds; the Vendor provides status updates.

*Antecedent:* `engage_case` is present in the ledger.

### 6. Vendor develops and ships a fix

The Vendor's engineering team produces a fix.  When the fix is ready, the Vendor
notifies the case, advancing the CS VFD state to *fix-ready* (VFd).  Subsequent
participant status updates reflect the new VFD state.

*Antecedent:* `engage_case` is present in the ledger.

### 7. Vulnerability is publicly disclosed

The Vendor publishes a security advisory.
The Reporter also publishes.
These publication events advance the CS PXA state to *publicly known* and trigger embargo teardown (EM exits ACTIVE).
Each publication notification is recorded as a participant status update in the ledger.
No participant deploys a fix in this scenario: deployment is a Deployer's step, so the Vendor's VFD state stays at fix-ready (VFd).

*Antecedent:* The fix-ready participant status entry is in the ledger.

### 8. All participants close the case

Both the Reporter and the Vendor indicate that their participation in the case is complete.
Each departure is recorded as a `close_case` entry in the ledger, followed by one participant status entry for each step the Case Actor takes to move that participant to RM `CLOSED`.
A replica moves the participant only by applying those status entries; a participant never records its own closure.
A participant that has closed receives its own `close_case` entry and the status entries for its own closure, and nothing after them.
The Reporter leaves first.
After its closure, the Reporter receives no further entries, so it does not learn of the Vendor's departure.
The Vendor is the Case Owner, so it leaves last: its departure also closes the case, and a departure sent after that is not recorded.
The Case Actor records its own closure as a participant status entry, then records `case_fully_closed`, the last entry for a participant's act.
The Vendor has already closed when the Case Actor writes these two entries, so the Vendor does not receive them.
The Case Actor's own ledger is where the closure of every participant is recorded.

*Antecedent:* `validate_report` and `engage_case` are both present in the ledger.
The Vendor's `close_case` follows the Reporter's.

## Unobservable edges

| Unobservable step | Why not in ledger |
|---|---|
| Reporter submits report to Vendor | Report submission is an out-of-band API call; the case does not yet exist when the report is submitted. |
