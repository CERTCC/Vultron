---
stakeholder_type: [platform-developer]
level: 300
---

# How to Post a Status Update or a Case Note

Use this guide to tell the other participants something: that your fix is ready, that the vulnerability is now public, or anything that needs narrative rather than a state change.
Each of these follows the same two-step shape — `as:Create` mints the object and `as:Add` attaches it.
You finish with the update committed to the case ledger and replicated to every participant.

---

## Prerequisites

{% include-markdown "./_demo_prerequisites.md" %}

- A case you are seated on, and your own `CaseParticipant` record.
- For a participant status, the dimension you are reporting: `vf_state` and `d_state` apply only to a Vendor or a Deployer.

---

## Report your own progress

Use a participant status for anything that is true of you rather than of the case.

Vendor Awareness (CV), Fix Readiness (CF) and Fix Deployed (CD) are all implemented in ActivityStreams as `Add(ParticipantStatus)`.
Which one you are sending is determined by the field you set, not by a different activity.

In every case, first send `Create(ParticipantStatus)` carrying the new value, then send `Add(ParticipantStatus)` targeting your own participant record.

### Report that a vendor now knows

Set `vf_state` from `vf` to `Vf`.
That is Vendor Awareness (CV).

### Report that a fix is ready

Set `vf_state` from `Vf` to `VF`.
That is Fix Readiness (CF).

### Report that a fix is deployed

Set `d_state` from `d` to `D`.
That is Fix Deployed (CD).

Send only your own status.
Participant status is self-declaratory, so a participant asserting another participant's state is a protocol violation outside the narrow externally-evidenced exceptions (ADR-0084).

---

## Report something true of the case

Use a case status for public awareness, exploit publication, and observed attacks — the dimensions that are properties of the vulnerability rather than of any one participant.

Public Awareness (CP), Exploit Public (CX) and Attacks Observed (CA) are all implemented in ActivityStreams as `Add(CaseStatus)`.
All three set `pxa_state`; which one you are sending is determined by which letter in it changes case.

In every case, first send `Create(CaseStatus)` carrying the new `pxa_state` and naming the case in `context`, then send `Add(CaseStatus)` naming the case in `target`.

### Report that the vulnerability is public

Change `p` to `P` in `pxa_state`.
That is Public Awareness (CP).

### Report that an exploit is public

Change `x` to `X`.
That is Exploit Public (CX).

### Report that attacks are happening

Change `a` to `A`.
That is Attacks Observed (CA).

The state change hangs off the `Add`, because that is the activity that asserts the attachment.

!!! warning "The case goes in `context` on the `Create` and `target` on the `Add`"

    That asymmetry is what the two patterns discriminate on: `Create(CaseStatus)` is recognized by its `context`, `Add(CaseStatus)` by its `target`.
    A `Create(CaseStatus)` that names the case in `target` instead matches neither pattern — it dispatches as unrecognized and the state change never happens.
    Send the `Add`, with the status inline if you prefer one activity to two.

---

## Post a note to the case

Use a note when the case needs narrative that no status field carries — a question, an answer, or a condition that needs human attention.
A note goes to the case participants, not to the public.

1. Draft the note: send `Create(Note)` with the note body.
2. Post it to the case: send `Add(Note)`, targeting the case.

The formal message set does not name this activity: it falls under the General Inquiry (GI) umbrella, which is a placeholder rather than a description — see [Why `GI` expands](../../../topics/activity_vocabulary_design.md#why-gi-expands-and-why-the-expansion-has-no-end).

If the note is a fault report rather than ordinary case discussion, see [How to Report a Protocol Fault](error.md).

---

## Verify

| What you sent | What to confirm |
|---|---|
| `Add(ParticipantStatus)` | Your participant record carries the new status, on every replica. |
| `Add(CaseStatus)` | The case status carries the new `pxa_state`, on every replica. |
| `Add(Note)` | The note appears on the case. |

Each of these is committed by the CASE_MANAGER and fanned out, so checking your own store alone does not confirm the update landed.

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

- [Case State (CS) Messages](../../../reference/messages/cs.md) — the wire format and a rendered example for each status activity, and which dimensions are participant-scoped
- [General Inquiry (GI) Messages](../../../reference/messages/general.md) — the wire format for the note lifecycle
- [Vultron AS Objects](../../../reference/activitypub/objects.md) — the ActivityStreams (AS) `CaseStatus`, `ParticipantStatus`, and `CaseParticipant` objects these activities carry
- [Activity Vocabulary Design](../../../topics/activity_vocabulary_design.md) — why the `Create` and `Add` split exists, and when an implementation may send only the `Add`
