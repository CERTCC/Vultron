---
title: "FV Scenario: Finder + Vendor"
status: stable
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
      Case engagement triggers the creation of participant status records for
      each actor that has joined.  The first status record establishes
      the participant's initial RM and CS state in the canonical ledger.
  - antecedent: validate_report
    consequent: close_case
    consequent_actor: vendor
    note: >
      The case must have been validated before it can be closed; a case that
      was never validated is not a real coordinated-disclosure lifecycle.
  - antecedent: engage_case
    consequent: add_note_to_case
    consequent_actor: finder
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
---

# FV Scenario: Finder + Vendor

## Overview

The FV scenario is the baseline two-actor Coordinated Vulnerability Disclosure
workflow.  A **Finder** discovers a vulnerability and submits a report to the
affected **Vendor**.  The Vendor validates and engages the case, develops a
fix, publishes an advisory, and closes the case.  The Finder and Vendor work
directly with no coordinator.

**Participants:**

- **Finder** — discovers the vulnerability and submits the report; in the case it holds the Reporter role, because the protocol has no Finder role ([ADR-0078](../../adr/0078-retire-finder-role.md)).
- **Vendor** — receives the report; validates, engages, and owns the case.
- **Case Actor** — the actor that holds the [CASE_MANAGER](../case_lifecycle/case_manager_and_ledger.md) role for this case; it writes every canonical ledger entry and fans it out to the participants. The Vendor's platform hosts it, but its authority comes from the role, not from where it runs.

## Protocol narrative

### 1. Finder submits a vulnerability report to Vendor

The Finder becomes aware of a security vulnerability in a Vendor product and
initiates disclosure.  The Finder sends a report to the Vendor's reporting
endpoint.  This act is not directly recorded in the case ledger; it is the
trigger that causes the case to be created on the Vendor's side.

*Antecedent:* Finder possesses knowledge of the vulnerability and a channel to
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

Once the case is active, the Case Actor records the initial participant status
for each actor — Finder and Vendor — capturing their RM state and CVD role.
Each such record appears in the ledger as an `add_participant_status_to_participant`
entry.

*Antecedent:* `engage_case` is present in the ledger.

### 5. Finder and Vendor exchange notes

Participants communicate about the vulnerability through case notes.  Each note
is posted via the protocol and recorded as an `add_note_to_case` entry in the
ledger.  The Finder may ask about workarounds; the Vendor provides status updates.

*Antecedent:* `engage_case` is present in the ledger.

### 6. Vendor develops and ships a fix

The Vendor's engineering team produces a fix.  When the fix is ready, the Vendor
notifies the case, advancing the CS VFD state to *fix-ready* (VFd).  Subsequent
participant status updates reflect the new VFD state.

*Antecedent:* `engage_case` is present in the ledger.

### 7. Vulnerability is publicly disclosed

The Vendor publishes a security advisory.  The Finder also publishes.  These
publication events advance the CS PXA state to *publicly known* and trigger
embargo teardown (EM exits ACTIVE).  Each publication notification is recorded
as a participant status update in the ledger.  No participant deploys a fix in
this scenario: deployment is a Deployer's step, so the Vendor's VFD state stays
at fix-ready (VFd).

*Antecedent:* The fix-ready participant status entry is in the ledger.

### 8. All participants close the case

Both the Finder and the Vendor indicate that their participation in the case
is complete.  Each closure is recorded as a `close_case` entry in the ledger.
The Vendor is the case owner, so its departure also closes the case: the
Case Actor records its own closure as a participant status entry, then records
`case_fully_closed`.

*Antecedent:* `validate_report` and `engage_case` are both present in the ledger.

## Unobservable edges

| Unobservable step | Why not in ledger |
|---|---|
| Finder submits report to Vendor | Report submission is an out-of-band API call; the case does not yet exist when the report is submitted. |
