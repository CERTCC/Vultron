---
stakeholder_type: [platform-developer]
level: 400
---

# How to Post a Status Update or a Case Note

Use this guide to tell the other participants something: that your fix is ready, that the vulnerability is now public, or anything that needs narrative rather than a state change.
A status update is one `as:Add` that carries the new status inline and attaches it; a new note is one `as:Create` whose note names the case as its `context`.
You finish with the update committed to the case ledger and replicated to every participant.

---

## Prerequisites

{% include-markdown "./_demo_prerequisites.md" %}

- A case you are seated on, and your own `CaseParticipant` record.
- For a participant status, the dimension you are reporting: `vf_state` and `d_state` apply only to a Vendor or a Deployer.
  The letters in these fields are the substates of the [CVD Case State Model](../../../topics/process_models/cs/cs_model.md#cvd-case-substates).

---

## Report your own progress

Use a participant status for anything that is true of you rather than of the case.

Vendor Awareness (CV), Fix Readiness (CF) and Fix Deployed (CD) are all implemented in ActivityStreams as `Add(ParticipantStatus)`.
Which one you are sending is determined by the field you set, not by a different activity.

In every case, send `Add(ParticipantStatus)` targeting your own participant record, with the new status inline as its `object`.
This implementation does not support a separate `Create(ParticipantStatus)` before it, and an inbox refuses one as an unrecognized activity.

### Report that a vendor now knows

Set `vf_state` from `vf` to `Vf`.
That is Vendor Awareness (CV).

{% include-markdown "../../../reference/messages/_occasions/embeds/vendor-awareness.md" %}

### Report that a fix is ready

Set `vf_state` from `Vf` to `VF`.
That is Fix Readiness (CF).

{% include-markdown "../../../reference/messages/_occasions/embeds/fix-readiness.md" %}

### Report that a fix is deployed

Set `d_state` from `d` to `D`.
That is Fix Deployed (CD).

{% include-markdown "../../../reference/messages/_occasions/embeds/fix-deployed.md" %}

Send only your own status.
Participant status is self-declaratory, so a participant asserting another participant's state is a protocol violation outside the narrow externally-evidenced exceptions (PRM-06-001, ADR-0121).

---

## Report something true of the case

Use a case status for public awareness, exploit publication, and observed attacks — the dimensions that are properties of the vulnerability rather than of any one participant.

Public Awareness (CP), Exploit Public (CX) and Attacks Observed (CA) are all implemented in ActivityStreams as `Add(CaseStatus)`.
All three set `pxaState`; which one you are sending is determined by which letter in it changes case.

In every case, send `Add(CaseStatus)` naming the case in `target`, with the new status, carrying the new `pxaState`, inline as its `object`.
This implementation does not support a separate `Create(CaseStatus)` before it, and an inbox refuses one as an unrecognized activity.

### Report that the vulnerability is public

Change `p` to `P` in `pxaState`.
That is Public Awareness (CP).

{% include-markdown "../../../reference/messages/_occasions/embeds/public-awareness.md" %}

### Report that an exploit is public

Change `x` to `X`.
That is Exploit Public (CX).

{% include-markdown "../../../reference/messages/_occasions/embeds/exploit-public.md" %}

### Report that attacks are happening

Change `a` to `A`.
That is Attacks Observed (CA).

{% include-markdown "../../../reference/messages/_occasions/embeds/attacks-observed.md" %}

The state change hangs off the `Add`, because that is the activity that asserts the attachment.

---

## Post a note to the case

Use a note when the case needs narrative that no status field carries — a question, an answer, or a condition that needs human attention.
A note goes to the case participants, not to the public.

To post a new note, send one `Create(Note)` to the CASE_MANAGER.
Set the note's `context` to the case, and give the `Create` no `target`.
The CASE_MANAGER attaches the note to the case and commits a `create_note` entry to the case ledger.

{% include-markdown "../../../reference/messages/_occasions/embeds/create-note.md" %}

To attach a note that already exists, such as one created earlier or by another implementation, send `Add(Note)` targeting the case.
The CASE_MANAGER attaches it and commits an `add_note_to_case` entry.
A receiver also accepts a `Create(Note)` followed by an `Add(Note)` of the same note; the `Add` then changes nothing more.
This implementation's add-note trigger sends the `Create` alone.

{% include-markdown "../../../reference/messages/_occasions/embeds/add-note-to-case.md" %}

To withdraw a note, send `Remove(Note)` to the CASE_MANAGER, targeting the case.
The CASE_MANAGER accepts it from the note's author while that author is an active participant, or from the Case Owner, and refuses it from anyone else.

{% include-markdown "../../../reference/messages/_occasions/embeds/remove-note-from-case.md" %}

The formal message set does not name this activity: it falls under the General Inquiry (GI) umbrella, which is a placeholder rather than a description — see [Why `GI` expands](../../../topics/activity_vocabulary_design.md#why-gi-expands-and-why-the-expansion-has-no-end).

If the note is a fault report rather than ordinary case discussion, see [How to Report a Protocol Fault](error.md).

---

## Verify

| What you sent | What to confirm |
|---|---|
| `Add(ParticipantStatus)` | Your participant record carries the new status, on every replica. |
| `Add(CaseStatus)` | The case status carries the new `pxaState`, on every replica. |
| `Create(Note)` or `Add(Note)` | The note appears on the case, on every replica. |

Each of these is committed by the CASE_MANAGER and fanned out, so checking your own store alone does not confirm the update landed.

---

## See it end to end

!!! example "Try it: `vultron-demo status-updates`"

    {% include-markdown "./_demo_status_updates.md" %}

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
