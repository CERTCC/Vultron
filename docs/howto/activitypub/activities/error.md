# How to Report a Protocol Fault

Use this guide when a message you received cannot be processed as sent.
Vultron partitions fault reporting by **failure mode**, so your first job is to
decide which of three modes you are in, and your second is to send the activity
that mode calls for.
You finish with the sender informed of why the message failed, in a form it can
act on.

---

## Prerequisites

{% include-markdown "./_demo_prerequisites.md" %}

- The message that failed, and the sender's actor URI.
- Your own determination of why it failed. The three modes below are mutually
  exclusive.

---

## Choose the failure mode

| Failure mode | Send |
|---|---|
| Received but **not understood** — format error, unknown type, parse failure | `Create(ProcessingFault)` |
| Received and understood but **declined** — invalid state, rule violation, unauthorized | `as:Reject` |
| Received and understood, but the condition needs **narrative explanation** | `CreateNote` and `AddNoteToCase` |

Three mechanisms cover every case (MSM-05-001).

- If you could not parse the message, send `Create(ProcessingFault)`. Do not
  reject it — rejection claims you understood it.
- If you understood the message and are refusing it, send `as:Reject`. Say which
  rule or state made it inadmissible.
- If the condition needs a human to read it, add a note to the case. See
  [How to Publish a Status Update or a Note](status_updates.md).

The failure mode is the actionable axis.
Knowing a message was not understood tells the sender to check its serialization;
knowing it was declined tells the sender to check the protocol state it assumed.

---

## Interpret an incoming `as:Reject`

`as:Reject` carries ordinary protocol refusals as well as faults —
`close_report`, `reject_invite_to_embargo_on_case`,
`reject_invite_actor_to_case`, `reject_case_proposal`, and
`reject_case_ownership_transfer` among them.

Read the object and the context before treating a `Reject` as an error.

!!! warning "Never infer a fault from the verb alone"

    A receiver MUST NOT infer error semantics from `as:Reject` by itself
    (MSM-05-003).
    Treating every `Reject` as a fault turns each legitimate refusal into a false
    alarm.

A `Reject(CaseLedgerEntry)` is a third thing again: it is the ledger negative
acknowledgement, and it asks the CASE_MANAGER to replay a missing prefix rather
than reporting a fault.
See
[Faults and Acknowledgements](../../../reference/messages/faults_and_acknowledgements.md).

---

## Verify

The sender holds your fault report, and the exchange that failed has not advanced
any state on your side.
A fault report is not a state transition.

---

## Further reading

- [Faults and Acknowledgements](../../../reference/messages/faults_and_acknowledgements.md)
  — the wire format for each mechanism, and why the formal `RE`, `EE`, `CE`, and
  `GE` shorthands have no dedicated wire activity
- [Activity Vocabulary Design](../../../topics/activity_vocabulary_design.md) —
  why the implementation partitions faults by failure mode rather than by state
  machine
- [Message Types](../../../reference/formal_protocol/messages.md) — the formal
  error shorthands these mechanisms realize

!!! note "Name collision"

    `VultronError` in `vultron/errors.py` is a Python exception base class.
    It is unrelated to the protocol wire-level fault activities above.
