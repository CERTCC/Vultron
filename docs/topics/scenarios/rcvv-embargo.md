---
title: "RCVV Embargo Scenario: Reporter + Coordinator + Vendor1 + Vendor2"
causal_edges:
  - antecedent: validate_report
    consequent: engage_case
    consequent_actor: coordinator
    note: >
      The Coordinator must validate the Reporter's report before engaging the case.
  - antecedent: engage_case
    consequent: invite_actor_to_case
    consequent_actor: case-actor
    note: >
      The Coordinator invites each Vendor only after the case is active.
      The Reporter is seated when the case is created and is not invited.
  - antecedent: invite_actor_to_case
    consequent: accept_invite_actor_to_case
    consequent_actor: vendor2
    note: >
      Vendor2 can only accept an invitation that has been sent.
      Accepting also makes Vendor2 a signatory to the embargo then in force.
  - antecedent: engage_case
    consequent: invite_to_embargo_on_case
    note: >
      The Reporter revises the default embargo only once the case is engaged.
      Each proposal, and the invitations the CASE_MANAGER relays to the other
      participants, are all recorded under this semantic type.
  - antecedent: invite_to_embargo_on_case
    consequent: accept_invite_to_embargo_on_case
    note: >
      An embargo proposal is answered only after it was made and relayed.
      Each acceptance records only its sender's consent.
  - antecedent: invite_to_embargo_on_case
    consequent: activate_embargo_on_case
    consequent_actor: coordinator
    note: >
      The Coordinator, as case owner, activates a revision only after it was
      proposed and relayed; the activation is its own decision for the case.
  - antecedent: activate_embargo_on_case
    consequent: remove_embargo_event_from_case
    note: >
      The embargo collapses only after the last revision was activated: the
      Reporter's publication then ends it automatically.
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
subject: implementation
---

# RCVV Embargo Scenario: Reporter + Coordinator + Vendor1 + Vendor2

## Overview

The RCVV embargo scenario follows an embargo through a revision cycle, a late second vendor and an accidental collapse.
A **Reporter** submits a report to a **Coordinator**, who opens the case and invites a first **Vendor**.
Creating the case activates the default embargo.
So the proposal of the Reporter and the later proposal of the first Vendor each revise an embargo that is already in force.

The Coordinator invites a second Vendor only after both revisions are active.
When the second Vendor accepts the invitation, it signs the embargo then in force.
When the Reporter reports public disclosure, the embargo ends on its own.
No participant terminates it.

**Participants:**

- **Reporter** — discovers the vulnerability, submits the report, proposes new embargo terms and later publishes.
- **Coordinator** — receives the report, then validates, engages and owns the case.
  It activates each revision.
- **Vendor1** — joins by invitation, consents to the first revision, proposes the second and develops a fix.
- **Vendor2** — joins late, signs the embargo in force and develops a fix.
- **Case Actor** — the actor that holds the [CASE_MANAGER](../case_lifecycle/case_manager_and_ledger.md) role for this case.
  It commits every embargo decision to the ledger and relays each proposal to the other participants.

## Protocol narrative

### 1. Report submission

The Reporter submits the report, the Coordinator validates it and engages the case, and Vendor1 joins by invitation.
The default embargo is active from case creation, so the case is at Embargo Management (EM) state `ACTIVE`.

*Antecedent:* Reporter has knowledge of the vulnerability.

### 2. Embargo proposal

The Reporter proposes new embargo terms.
The proposal goes only to the CASE_MANAGER.
The CASE_MANAGER moves the case to EM `REVISE`, records the proposal and relays it to the Coordinator and Vendor1.

Vendor1 accepts, which records its consent and changes no EM state.
The Coordinator, as case owner, answers with its decision for the case.
It activates the revision, and the case returns to EM `ACTIVE`.

Each participant waits for the relayed invitation on its own replica.
No participant waits for a message from another participant.

With the revised embargo in force, the Reporter asks about it in a case note, and Vendor1 answers.
In this scenario the Reporter proposes terms before it asks anything, and Vendor1's next decision comes after its answer.

*Antecedent:* the case is engaged and EM is `ACTIVE`.

### 3. Embargo revision

Vendor1 proposes further terms.
The CASE_MANAGER relays the proposal to the Reporter and the Coordinator.
The Reporter accepts, and the Coordinator, as owner, activates the revision.

*Antecedent:* the first revision is active.

### 4. Vendor2 late invite

The Coordinator invites Vendor2 only after the second revision is active.
Accepting the invitation records Vendor2's consent to the embargo in force, so Vendor2 is a signatory before it does anything else.

*Antecedent:* the second revision is active.

### 5. Fix lifecycle

Both vendors report the fix ready.
The embargo does not change.

*Antecedent:* Vendor2 is a signatory to the active embargo.

### 6. Accidental collapse

The Reporter reports public disclosure.
The report moves the case to the public-aware state, and the CASE_MANAGER ends the embargo in response.

EM moves to `EXITED` on the canonical case.
EM then moves to `EXITED` on each replica when the ledger entry reaches it.
Nothing requests the termination.
The protocol itself collapses the embargo as a consequence of the disclosure.

*Antecedent:* the fixes are ready.

### 7. Case closure

Every participant closes the case.
Vendor1, the Reporter, and Vendor2 leave first.
The Coordinator, the Case Owner, leaves last.
{% include-markdown "./_owner_leaves_last.md" trailing-newlines=false %}

*Antecedent:* the vulnerability has been published.

### 8. Ledger dump

The scenario writes each participant's case ledger for the invariant harness, on success and on failure.
