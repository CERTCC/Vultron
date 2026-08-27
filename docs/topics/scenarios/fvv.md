---
title: "FVV Scenario: Finder + Vendor1 + Vendor2"
status: stable
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
    consequent_actor: vendor
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
  - antecedent: engage_case
    consequent: add_note_to_case
    consequent_actor: finder
    note: >
      Notes are substantive protocol communications within an active case.
  - antecedent: report_submitted
    consequent: validate_report
    consequent_actor: vendor
    observable: false
    note: >
      The Finder's initial report submission is an out-of-band API call;
      no ledger entry exists until validation occurs.
---

# FVV Scenario: Finder + Vendor1 + Vendor2

## Overview

The FVV scenario extends the baseline FV workflow to include a **second
affected Vendor** (Vendor2).  Vendor1 creates the case and directly invites
Vendor2 by sending an invitation through the protocol.  Both vendors have
independent fix paths and must each reach the fix-ready state before disclosure.

**Participants:**

- **Finder** — discovers the vulnerability; submits the initial report.
- **Vendor1** — receives the report; validates, engages, and initially owns the case.
- **Vendor2** — invited by Vendor1; an additional affected party with its own fix path.
- **CaseActor** — Vendor1's internal case-management sub-actor.

## Protocol narrative

### 1. Finder submits a vulnerability report to Vendor1

The Finder identifies a vulnerability affecting products from both Vendor1 and
Vendor2 and reports it to Vendor1 as the primary contact.  This report
submission is an out-of-band event; it precedes the case's creation.

*Antecedent:* Finder possesses knowledge of the vulnerability.

### 2. Vendor1 validates and engages the case

Vendor1 reviews the report, confirms it is credible and in scope, and engages
the case.  A `validate_report` entry and an `engage_case` entry appear in the
case ledger in that order.

*Antecedent:* Report received from Finder (step 1).

### 3. Participant status records are created

The CaseActor records the initial participant status for Finder and Vendor1
as `add_participant_status_to_participant` entries.

*Antecedent:* `engage_case` is present in the ledger.

### 4. Vendor1 invites Vendor2

After confirming that Vendor2 is affected, Vendor1 sends Vendor2 an invitation
to join the case.  This is recorded as an `invite_actor_to_case` entry.

*Antecedent:* `engage_case` is present in the ledger.

### 5. Vendor2 accepts the invitation

Vendor2 receives and reviews the invitation and decides to participate.  The
acceptance is recorded as an `accept_invite_actor_to_case` entry.

*Antecedent:* `invite_actor_to_case` is present in the ledger (step 4).

### 6. Participants exchange notes

Finder, Vendor1, and Vendor2 communicate via case notes.  Each note is recorded
as `add_note_to_case`.

*Antecedent:* `engage_case` is present in the ledger.

### 7. Both vendors develop and ship fixes

Vendor1 and Vendor2 each advance through the fix lifecycle independently.  Both
reach fix-ready (VFd) state; participant status updates reflect progress.

*Antecedent:* `engage_case` is present in the ledger.

### 8. Vendors and Finder publish; embargo terminates

All three participants publish.  The embargo exits ACTIVE.  The CS PXA state
advances towards publicly-known for each participant.

*Antecedent:* Both vendors have reached fix-ready status.

### 9. All participants close the case

Vendor1, Vendor2, and Finder each close the case.  `close_case` entries appear
for each.

*Antecedent:* `validate_report` and `engage_case` are in the ledger.

## Unobservable edges

| Unobservable step | Why not in ledger |
|---|---|
| Finder submits report to Vendor1 | Report submission is an out-of-band API call that precedes the case's creation. |
