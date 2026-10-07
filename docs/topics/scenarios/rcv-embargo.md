---
title: "RCV Embargo Scenario: Reporter + Coordinator + Vendor"
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
      The Coordinator invites the Vendor only after the case is active.
      The Reporter is seated when the case is created and is not invited.
  - antecedent: invite_actor_to_case
    consequent: accept_invite_actor_to_case
    consequent_actor: vendor
    note: >
      A participant can only accept an invitation that has been sent.
  - antecedent: engage_case
    consequent: invite_to_embargo_on_case
    note: >
      The Reporter revises the default embargo only once the case is engaged.
      The proposal and the invitations the CASE_MANAGER relays to the other
      participants are all recorded under this event type.
  - antecedent: invite_to_embargo_on_case
    consequent: accept_invite_to_embargo_on_case
    note: >
      An embargo proposal is answered only after it was made and relayed.
      The case owner's acceptance, which activates the revision, is among the
      acceptances recorded.
  - antecedent: accept_invite_to_embargo_on_case
    consequent: remove_embargo_event_from_case
    note: >
      The Coordinator ends the embargo that the owner's acceptance activated.
  - antecedent: validate_report
    consequent: close_case
    consequent_actor: coordinator
    note: >
      Closure requires a validated, engaged case.
  - antecedent: report_submitted
    consequent: validate_report
    consequent_actor: coordinator
    observable: false
    note: >
      The Reporter's report submission to the Coordinator is an out-of-band API
      call that precedes the case.
stakeholder_type: [platform-developer, project-contributor]
level: 300
---

# RCV Embargo Scenario: Reporter + Coordinator + Vendor

## Overview

The RCV embargo scenario follows the embargo from end to end in a three-party case.
A **Reporter** submits a report to a **Coordinator**, who opens the case and invites a **Vendor**.
Creating the case activates the default embargo, so the Reporter's later proposal revises that embargo rather than starting a first one.
The Coordinator then ends the embargo deliberately, before the vulnerability is published.

**Participants:**

- **Reporter** — discovers the vulnerability, submits the report and proposes new embargo terms.
- **Coordinator** — receives the report; validates, engages and owns the case; activates the revised embargo and later ends it.
- **Vendor** — joins by invitation, consents to the revision and develops the fix.
- **Case Actor** — the actor that holds the [CASE_MANAGER](../case_lifecycle/case_manager_and_ledger.md) role for this case; it commits every embargo decision to the ledger and relays each proposal to the other participants.

## Protocol narrative

### 1. Report submission

The Reporter submits the report, the Coordinator validates it and engages the case, and the Vendor joins by invitation.
The default embargo is active from case creation, so the case is at EM `ACTIVE`.

*Antecedent:* Reporter has knowledge of the vulnerability.

### 2. Embargo proposal

The Reporter proposes new embargo terms.
The proposal goes to the CASE_MANAGER only, which moves the case to EM `REVISE`, records the proposal and relays it to the Coordinator and the Vendor.
The Vendor accepts, which records its consent and changes no EM state.
The Coordinator, as case owner, accepts, which activates the revision and returns the case to EM `ACTIVE`.
Each participant waits for the relayed invitation on its own replica; none waits for another participant's message.

*Antecedent:* the case is engaged and EM is `ACTIVE`.

### 3. Fix lifecycle

The Vendor reports the fix ready.
The embargo is untouched.

*Antecedent:* the revised embargo is active.

### 4. Embargo termination

The Coordinator terminates the embargo.
The CASE_MANAGER records the termination and EM moves to `EXITED` on the canonical case, then on each replica as the ledger entry reaches it.

*Antecedent:* the revised embargo is active.

### 5. Publication

Every participant reports publication.
The embargo has already ended, so publication tears nothing down and EM stays `EXITED`.

*Antecedent:* the embargo has ended.

### 6. Case closure

Every participant closes the case.

*Antecedent:* the vulnerability has been published.

### 7. Ledger dump

The scenario writes each participant's case ledger for the invariant harness, on success and on failure.
