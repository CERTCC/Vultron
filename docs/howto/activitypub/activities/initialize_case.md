---
stakeholder_type: [platform-developer]
level: 300
---

# How to Initialize a Case

Use this guide to open a `VulnerabilityCase` after validating a report.
Initialization seats the case, attaches at least one report, seats at least one participant, and attaches any opening notes.
You finish with a case whose roster and report are in place and whose ledger has its genesis entry.

---

## Prerequisites

{% include-markdown "./_demo_prerequisites.md" %}

- A report at Report Management (RM) state `RM.VALID`.
  See [How to Report a Vulnerability](report_vulnerability.md).
- The actor Uniform Resource Identifiers (URIs) of any participants you already know about, such as the Reporter.

---

## The exchange

The flowchart below shows the four activities case initialization can use.
The three `as:Add` activities branch from `Create(VulnerabilityCase)` because each attaches a different kind of object to the new case.

```mermaid
---
title: Case Creation and the Objects Attached to It
---
flowchart LR
    subgraph as:Create
        CreateCase["Create Case<br/>Create(VulnerabilityCase)"]
    end
    subgraph as:Add
        AddReportToCase["Add Report to Case<br/>Add(VulnerabilityReport)"]
        AddParticipantToCase["Add Case Participant to Case<br/>Add(CaseParticipant)"]
        AddNoteToCase["Post a note to the case<br/>Add(Note)"]
    end
    CreateCase --> AddReportToCase
    CreateCase --> AddParticipantToCase
    CreateCase --> AddNoteToCase
```

---

## Seat the case

1. Send `Create(VulnerabilityCase)`, carrying the new `VulnerabilityCase` as its `object`.
   Set yourself as Case Owner.
2. Attach the report with `Add(VulnerabilityReport)`, targeting the case.
3. Seat each participant you already know with `Add(CaseParticipant)`, targeting the case.
4. If the case needs opening context, attach it with `Add(Note)`.
   See [How to Post a Status Update or a Case Note](status_updates.md).

If every report, participant, and note is known when you create the case, carry them inline on the `Create(VulnerabilityCase)` activity and skip steps 2 through 4.
The steps are separated here because they are easier to follow one at a time, not because a conformant implementation must emit them individually.

If a participant becomes known later, seat it with its own activity pair — see [How to Seat a Participant on an Existing Case](initialize_participant.md).
If the actor has not agreed to join, invite it instead: [How to Invite an Actor to a Case](invite_actor.md).

!!! warning "A second report needs its own `Add`"

    A case can accumulate reports.
    When a second report arrives for a case that already has one, attach it with `Add(VulnerabilityReport)` rather than creating a new case.

---

## Verify

| What you sent | What to confirm |
|---|---|
| `Create(VulnerabilityCase)` | The case exists and names you as Case Owner. |
| `Add(VulnerabilityReport)` | The case lists the report. |
| `Add(CaseParticipant)` | The case roster holds the participant with its roles. |
| `Add(Note)` | The note appears on the case. |

Every one of these is committed to the case ledger by the CASE_MANAGER and fanned out to each participant, so each participant's replica should show the same roster.

---

## See it end to end

!!! example "Try it: `vultron-demo initialize-case`"

    ```bash
    vultron-demo initialize-case
    ```

    Or with Docker Compose:

    ```bash
    DEMO=initialize-case docker compose -f docker/docker-compose.yml run --rm demo
    ```

---

## Further reading

- [Case Management Messages](../../../reference/messages/case_management.md) — the wire format and a rendered example for each activity above
- [Activity Vocabulary Design](../../../topics/activity_vocabulary_design.md) — why creation and attachment are separate verbs, and when inlining an object is worth having
- [Case Ledger Synchronization](../../../topics/case_lifecycle/case_ledger_sync.md) — how the activities above reach every participant's replica
