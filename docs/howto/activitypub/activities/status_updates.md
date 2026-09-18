# How to Publish a Status Update or a Note

Use this guide to tell the other participants something: that your fix is ready,
that the vulnerability is now public, or anything that needs narrative rather
than a state change.
Each of these follows the same two-step shape — `as:Create` mints the object and
`as:Add` attaches it.
You finish with the update committed to the case ledger and replicated to every
participant.

---

## Prerequisites

{% include-markdown "./_demo_prerequisites.md" %}

- A case you are seated on, and your own `CaseParticipant` record.
- For a participant status, the dimension you are reporting: `vf_state` and
  `d_state` apply only to a Vendor or a Deployer.

---

## Report your own progress

Use a participant status for anything that is true of you rather than of the
case.

1. Send `CreateParticipantStatus`, carrying your `rm_state` and, where they
   apply, `vf_state` and `d_state`.
2. Send `AddStatusToParticipant`, targeting your own participant record.

Send only your own status.
Participant status is self-declaratory, so a participant asserting another
participant's state is a protocol violation outside the narrow
externally-evidenced exceptions (ADR-0084).

---

## Report something true of the case

Use a case status for public awareness, exploit publication, and observed
attacks — the dimensions that are properties of the vulnerability rather than of
any one participant.

1. Send `CreateCaseStatus`, carrying the new `pxa_state`, and name the case in
   `context`.
2. Send `AddStatusToCase`, naming the case in `target`.

The state change hangs off the `Add`, because that is the activity that asserts
the attachment.

!!! warning "The case goes in `context` on the `Create` and `target` on the `Add`"

    That asymmetry is what the two patterns discriminate on:
    `Create(CaseStatus)` is recognized by its `context`, `Add(CaseStatus)` by its
    `target`.
    A `Create(CaseStatus)` that names the case in `target` instead matches
    neither pattern — it dispatches as unrecognized and the state change never
    happens.
    Send the `Add`, with the status inline if you prefer one activity to two.

---

## Add a note

Use a note when the case needs narrative that no status field carries — a
question, an answer, or a condition that needs human attention.

1. Send `CreateNote` with the note body.
2. Send `AddNoteToCase`, targeting the case.

If the note is a fault report rather than ordinary case discussion, see
[How to Report a Protocol Fault](error.md).

---

## Verify

| What you sent | What to confirm |
|---|---|
| `AddStatusToParticipant` | Your participant record carries the new status, on every replica. |
| `AddStatusToCase` | The case status carries the new `pxa_state`, on every replica. |
| `AddNoteToCase` | The note appears on the case. |

Each of these is committed by the CASE_MANAGER and fanned out, so checking your
own store alone does not confirm the update landed.

---

## See it end to end

!!! example "Try it: `vultron-demo status-updates`"

    ```bash
    vultron-demo status-updates
    ```

    Or with Docker Compose:

    ```bash
    DEMO=status-updates docker compose -f docker/docker-compose.yml run --rm demo
    ```

    The scenario adds a note, a case status, and a participant status.

---

## Further reading

- [Case State (CS) Messages](../../../reference/messages/cs.md) — the wire format
  and a rendered example for each status activity, and which dimensions are
  participant-scoped
- [General (GI) Messages](../../../reference/messages/general.md) — the wire
  format for the note lifecycle
- [Vultron AS Objects](../../../reference/activitypub/objects.md) — the
  `CaseStatus`, `ParticipantStatus`, and `CaseParticipant` objects these
  activities carry
- [Activity Vocabulary Design](../../../topics/activity_vocabulary_design.md) —
  why the `Create` and `Add` split exists, and when an implementation may send
  only the `Add`
