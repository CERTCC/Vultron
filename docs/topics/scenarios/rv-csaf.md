---
title: "rv-csaf Scenario: Reporter + Vendor, a Case from a CSAF Report"
causal_edges:
  - antecedent: validate_report
    consequent: engage_case
    consequent_actor: vendor
    note: >
      The vendor cannot engage the case until the report has been validated.
  - antecedent: engage_case
    consequent: add_participant_status_to_participant
    consequent_actor: case-actor
    note: >
      The Case Actor records each engagement's RM ACCEPTED as a participant
      status entry right after the engage_case entry (CLP-07-013).
  - antecedent: invite_to_embargo_on_case
    consequent: accept_invite_to_embargo_on_case
    consequent_actor: reporter
    note: >
      The CSAF disclosure date won under shortest-wins, so the Case Actor
      relays the Vendor's longer default to the Reporter, whose terms won, as
      a revision invitation (EP-04-027).  The Reporter's acceptance answers
      that invitation.
  - antecedent: engage_case
    consequent: add_note_to_case
    consequent_actor: reporter
    note: >
      Protocol notes are substantive communications within an active case;
      they cannot precede case engagement.
  - antecedent: validate_report
    consequent: close_case
    consequent_actor: vendor
    note: >
      The case must have been validated before it can be closed.
  - antecedent: close_case
    consequent: close_case
    consequent_actor: vendor
    note: >
      The Vendor, the Case Owner, leaves last (CM-23-015): the Reporter's
      close_case precedes the owner's.
  - antecedent: report_submitted
    consequent: validate_report
    consequent_actor: vendor
    observable: false
    note: >
      The Reporter's submission, with its CSAF document attached, is not a
      case-ledger entry: the case does not exist yet.
stakeholder_type: [platform-developer, project-contributor]
level: 300
page_type: reference
subject: implementation
---

# `rv-csaf` Scenario: Reporter + Vendor, a Case from a CSAF Report

## Overview

The `rv-csaf` scenario shows a case that starts from a CSAF 2.1 vulnerability report.
The **Reporter** sends the **Vendor** a report with a CSAF document attached, and states no report name, no summary and no embargo end.
The case takes all three from the document: its name is the document's title, its summary is the document's summary note, and its embargo ends at the document's disclosure date.
After the case starts, the scenario goes on as the [`rv`](rv.md) scenario does.

**Participants:**

- {% include-markdown "./_participant_reporter.md" trailing-newlines=false %}
- **Vendor** — publishes a default embargo, receives the report, validates it, and owns the case.
- {% include-markdown "./_participant_case_actor.md" trailing-newlines=false %}

## Protocol narrative

### 1. Vendor publishes a default embargo

Before the report arrives, the Vendor publishes a 30-day default embargo on its own actor profile.
This default is what the Reporter's terms compete with when the case is created.
The policy is not a case-ledger entry, because the case does not exist yet.

### 2. Reporter sends a CSAF vulnerability report

The Reporter writes a CSAF 2.1 document of category `csaf_vulnerability_report`.
The document has a title, a summary note, and one vulnerability whose disclosure date is 10 days away.
The Reporter calls its submit-report trigger with the document attached and with no report name, summary or embargo end.
The trigger checks the document against the CSAF 2.1 schema and refuses a document that is not schema-valid.
The trigger then fills the report's name and summary from the document, and proposes an embargo that ends at the document's disclosure date.
The Vendor receives an Offer that carries the report, the document and the proposed embargo.

*Antecedent:* the Reporter has a CSAF document that this project wrote, schema-valid against the pinned CSAF 2.1 revision.

### 3. Vendor validates the report and engages the case

The Vendor validates the report and engages the case, as in `rv`.
The Case Actor creates the case from the document on the Offer that the Vendor's case proposal carries.
The case's name is the document's title, and the case's summary is the document's summary note.
The two embargo terms compete by shortest-wins.
The document's 10-day term is shorter than the Vendor's 30-day default, so it becomes the active embargo.
The Vendor's default is registered as a pending revision, and the case starts at EM `REVISE`.
The Case Actor relays the revision to the Reporter, whose terms won, and the Reporter accepts it.

*Antecedent:* the Offer reached the Vendor (step 2).

### 4. The scenario checks the case against the document

The scenario reads the canonical case on the Case Actor's container.
It checks that the case's name is the document's title and its summary is the document's summary note.
It checks that the active embargo ends at the document's disclosure date, and that the pending revision runs the Vendor's 30-day default.

### 5. The case continues as in `rv`

The Reporter asks the Vendor about a workaround, and the Vendor answers.
The Vendor reports its fix ready.
The Vendor publishes, which ends the embargo, and then the Reporter publishes.
The Reporter closes the case, and then the Vendor, the Case Owner, closes it last.

*Antecedent:* `engage_case` is present in the ledger.

## Unobservable edges

| Unobservable step | Why not in ledger |
|---|---|
| Vendor publishes its default embargo | A policy on the Vendor's own profile; no case exists yet. |
| Reporter submits the CSAF report to the Vendor | Report submission is an out-of-band API call; the case does not yet exist when the report is submitted. |

## The story as the code tells it

{% include-markdown "./_rv-csaf-story.md" %}
