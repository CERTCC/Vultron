---
stakeholder_type: [platform-developer]
level: 400
---

# How to Post a Status Update or a Case Note

Use this guide to tell the other participants something: that your fix is ready, that the vulnerability is now public, or anything that needs narrative rather than a state change.
A status update is one `as:Add(ParticipantStatus)` that carries your new status inline and attaches it to your own participant record.
A note is sent the same way: one `as:Add` that carries the note inline.
You finish with the update committed to the case ledger and replicated to every participant.

---

## Prerequisites

{% include-markdown "./_demo_prerequisites.md" %}

- A case you are seated on, and your own `CaseParticipant` record.
- For a participant status, the dimension you are reporting: `vfState` and `dState` apply only to a Vendor or a Deployer.
  The letters in these fields are the substates of the [CVD Case State Model](../../../topics/process_models/cs/cs_model.md#cvd-case-substates).

---

## Report your own progress

Use a participant status for anything that is true of you rather than of the case.

Vendor Awareness (CV), Fix Readiness (CF) and Fix Deployed (CD) are all implemented in ActivityStreams as `Add(ParticipantStatus)`.
Which one you are sending is determined by the field you set, not by a different activity.

In every case, send `Add(ParticipantStatus)` targeting your own participant record, with the new status inline as its `object`.
Set the status's `context` to the case your participant record belongs to: the CASE_MANAGER acts on the case of the participant record you target, and refuses a status whose `context` names another case (HP-08-008).
The protocol names `Add(ParticipantStatus)` as the one form; a received `Create(ParticipantStatus)` is not a protocol message (VAM-01-011), and this implementation's inbox refuses it as an unrecognized activity (VAM-01-010).

### Report that a vendor now knows

Set `vfState` from `vf` to `Vf`.
That is Vendor Awareness (CV).

{% include-markdown "../../../reference/messages/_occasions/embeds/vendor-awareness.md" %}

### Report that a fix is ready

Set `vfState` from `Vf` to `VF`.
That is Fix Readiness (CF).

{% include-markdown "../../../reference/messages/_occasions/embeds/fix-readiness.md" %}

### Report that a fix is deployed

Set `dState` from `d` to `D`.
That is Fix Deployed (CD).

{% include-markdown "../../../reference/messages/_occasions/embeds/fix-deployed.md" %}

Send only your own status.
Participant status is self-declaratory, so a participant asserting another participant's state is a protocol violation outside the narrow externally-evidenced exceptions (PRM-06-001, ADR-0121).
The CASE_MANAGER refuses an `Add(ParticipantStatus)` that targets another participant's record, whatever it carries, and commits nothing (RSH-08-007).
The only exceptions are the on-behalf assertions: a CASE_MANAGER or Case Owner may move a vendor from `vf` to `Vf`, or a deployer from `d` to `D`, if the status changes nothing else (PRM-06-003, PRM-06-004).

---

## Report something true of the case

Public awareness, exploit publication, and observed attacks are properties of the vulnerability rather than of any one participant.
You report your own view of them in your participant status.

Public Awareness (CP), Exploit Public (CX) and Attacks Observed (CA) all set `pxaState` in the case status that your participant status embeds.
Which one you are sending is determined by which letter in it changes case.

Send `Add(ParticipantStatus)` targeting your own participant record, with the new status inline as its `object`, and make the change to `pxaState` in its embedded case status.
Only the CASE_MANAGER sends `Add(CaseStatus)`, inside a case ledger entry, as its record of the case status it adopted (RSH-04-001).
A receiver refuses an `Add(CaseStatus)` from any other sender (RSH-04-005).

### Report that the vulnerability is public

Change `p` to `P` in `pxaState`.
That is Public Awareness (CP).

{% include-markdown "../../../reference/messages/_occasions/embeds/participant-public-awareness.md" %}

### Report that an exploit is public

Change `x` to `X`.
That is Exploit Public (CX).

{% include-markdown "../../../reference/messages/_occasions/embeds/participant-exploit-public.md" %}

### Report that attacks are happening

Change `a` to `A`.
That is Attacks Observed (CA).

{% include-markdown "../../../reference/messages/_occasions/embeds/participant-attacks-observed.md" %}

### What happens to your report

Your report is your view of the case status, not a change to it.
The CASE_MANAGER takes your participant status whole or refuses it whole: if one value cannot be accepted, nothing in the update is recorded, and its refusal notice names every value it refused and why (RSH-09-002).
The CASE_MANAGER records the status on your participant record and chooses whether to adopt the reported `pxaState` for the case, by default only with the Case Owner's authorization (RSH-07-001).
If it adopts the change, the CASE_MANAGER commits it as an `Add(CaseStatus)` entry to the case ledger.
While an embargo is active or proposed, it then ends or abandons the embargo (RSH-03-001).
The Reporter + Vendor (`rv`) demo and the `status-updates` demo report public awareness this way.

---

## Post a note to the case

Use a note when the case needs narrative that no status field carries — a question, an answer, or a condition that needs human attention.
A note goes to the case participants, not to the public.

To post a note, send one `Add(Note)` to the CASE_MANAGER, targeting the case, with the note carried inline as its `object`.
Set the note's `context` to the case as well: the CASE_MANAGER refuses a note whose `context` names another case, or names none (HP-08-007).
Give each note a new id: an `Add(Note)` introduces a note, so the CASE_MANAGER refuses one whose note id it already holds, whatever the note says (HP-08-006).
Changing a posted note would be an `Update(Note)`, which this implementation does not handle yet.
A redelivery of the same `Add(Note)` changes nothing.

The CASE_MANAGER stores the note, attaches it to the case and commits an `add_note_to_case` entry to the case ledger.
The CASE_MANAGER accepts a note only from an active participant whose closure the case does not record, and refuses it from any other sender, including a closed participant (CM-23-018).
A refused note is not stored, attached, committed or sent on.
A participant's replica accepts a note only from the CASE_MANAGER.
`Add(Note)` is the one message that attaches a note (VAM-01-011).

{% include-markdown "../../../reference/messages/_occasions/embeds/add-note-to-case.md" %}

A received `Create` of a note is not a protocol message, and this implementation's inbox refuses it as an unrecognized activity (VAM-01-010).

To withdraw a note, send `Remove(Note)` to the CASE_MANAGER, targeting the case.
The CASE_MANAGER admits it from the note's author while that author is an active participant, or from the Case Owner, and refuses it from anyone else.

{% include-markdown "../../../reference/messages/_occasions/embeds/remove-note-from-case.md" %}

The formal message set does not name this activity: it falls under the General Inquiry (GI) umbrella, which is a placeholder rather than a description — see [Why `GI` expands](../../../topics/activity_vocabulary_design.md#why-gi-expands-and-why-the-expansion-has-no-end).

If the note is a fault report rather than ordinary case discussion, see [How to Report a Protocol Fault](error.md).

---

## Verify

| What you sent | What to confirm |
|---|---|
| `Add(ParticipantStatus)` | Your participant record carries the new status, on every replica. |
| `Add(ParticipantStatus)` carrying a `pxaState` | Once the CASE_MANAGER adopts it, the case status carries the new `pxaState`, on every replica. |
| `Add(Note)` | The note appears on the case, on every replica. |

Each of these is committed by the CASE_MANAGER and fanned out, so checking your own store alone does not confirm the update landed.

---

## See it end to end

!!! example "Try it: `vultron-demo status-updates`"

    {% include-markdown "./_demo_status_updates.md" %}

    Or with Docker Compose:

    ```bash
    DEMO=status-updates docker compose -f docker/docker-compose.yml run --rm demo
    ```

    The scenario adds and removes a note, then reports public awareness in a participant status and checks that the case status adopted it.

---

## Further reading

- [Case State (CS) Messages](../../../reference/messages/cs.md) — the wire format and a rendered example for each status activity, and which dimensions are participant-scoped
- [General Inquiry (GI) Messages](../../../reference/messages/general.md) — the wire format for the note lifecycle
- [Vultron AS Objects](../../../reference/activitypub/objects.md) — the ActivityStreams (AS) `CaseStatus`, `ParticipantStatus`, and `CaseParticipant` objects these activities carry
- [Activity Vocabulary Design](../../../topics/activity_vocabulary_design.md) — why the `Create` and `Add` split exists, and when an implementation may send only the `Add`
