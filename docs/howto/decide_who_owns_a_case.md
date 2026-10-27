---
description: >
  Select a path for a vulnerability: send a report, report to yourself and
  coordinate the case, or transfer a case. One question gives the path: who
  should be the Case Owner now, and who later?
stakeholder_type: [cvd-practitioner]
level: 200
page_type: how-to
subject: protocol
---

# How to Select the Case Owner

{% include-markdown "../includes/not_normative.md" %}

Use this guide when you have a vulnerability and must start a Coordinated Vulnerability Disclosure (CVD) case for it under Vultron.
You can send a report to a different organization.
You can also report to yourself and coordinate the case.
If you are the Case Owner of a case, you can transfer the case to a participant that is a better owner.
One question gives the correct path: who should be the [Case Owner](../reference/glossary.md#cvd-roles-and-participants) now, and who later?

---

## Prerequisites

- You know what a case is, which participant is its Case Owner, and which participant keeps its record.
  [A Case Under Vultron](../topics/case_lifecycle/a_case_under_vultron.md) gives this information.
- You know what an [embargo](../topics/process_models/em/principles.md) requires from the participants that agree to it.
- Your organization operates a system that sends and receives Vultron messages, or it can use one.

---

## Step 1: Know the four rules that control your selection

Four protocol rules control the result of each path.
Read these rules before you select a path.

**A case starts with a report and a proposal.**
No participant makes a case directly.
The actor that receives a report proposes a case to a [Case Actor Service](../reference/glossary.md#cvd-roles-and-participants).
That actor can be you.
The service makes the case, and it keeps the history of the case as its [Case Manager](../topics/case_lifecycle/case_manager_and_ledger.md).
The service makes the receiver of the report the Case Owner, and it adds the Reporter as a participant ([CP-09-001](../reference/specs/protocol.md#cp-09-001), [CP-09-002](../reference/specs/protocol.md#cp-09-002), [CM-22-001](../reference/specs/protocol.md#cm-22-001)).
Thus, the actor that receives the report is the Case Owner.

**An invitation adds a participant, not a Case Owner.**
When the Case Owner invites an actor, that actor becomes a participant with the roles that the invitation names ([§12.2 Invitation and Acceptance](../reference/vultron-spec/interactions.md#122-invitation-and-acceptance-n)).
A case has only one Case Owner at a time ([CM-21-001](../reference/specs/protocol.md#cm-21-001)).
The Case Owner role moves to a different participant only by an [ownership transfer](../topics/case_lifecycle/ownership_transfer.md) ([CM-21-002](../reference/specs/protocol.md#cm-21-002)).
The Case Manager refuses all other offers of the Case Owner role ([CM-33-003](../reference/specs/protocol.md#cm-33-003)).
If you make a case and invite the vendor, you continue to make the decisions for the case.

**The actor that reports is the Reporter.**
The protocol has no finder role ([ADR-0078](../adr/0078-retire-finder-role.md)).
The actor that reports a vulnerability gets the [Reporter](../reference/glossary.md#cvd-roles-and-participants) role.
This actor can be a [finder](../reference/glossary.md#cvd-roles-and-participants), a vendor that finds a vulnerability in its own product, or a coordinator.
The report records who found the vulnerability, and the role does not.

**When you send a report, you agree to the embargo of the case.**
When the Case Manager makes a case from your report, it adds you as a signatory to the active embargo, if there is one ([CM-14-005](../reference/specs/protocol.md#cm-14-005)).
You can propose your own embargo terms in the report ([EP-04-004](../reference/specs/protocol.md#ep-04-004)).
If the receiver also has default terms, the shorter embargo becomes active ([EP-04-003](../reference/specs/protocol.md#ep-04-003), [Default Embargoes](../topics/process_models/em/defaults.md)).
The longer embargo becomes a proposed revision.

---

## Step 2: Select a path

The four paths that follow go from the least work to the most work.
Use the first path whose condition is true for you.

| Path | Use it when | Case Owner |
|---|---|---|
| Send a report | The receiver should be the Case Owner and make the decisions | The receiver |
| Report to yourself and coordinate | You should be the Case Owner for all of the case | You |
| Report to yourself, invite the vendor, and make a decision later | You should be the Case Owner now, and possibly a different participant later | You, until you transfer the case |
| Transfer the ownership of a case | The case is open, and a different participant should now coordinate it | The participant that accepts the transfer |

### Send a report

Use this path if you agree that the receiver makes the decisions.
The receiver makes the decision to open a case, and it makes the decisions in the case.
This path is usual for a finder that reports to a vendor or a coordinator.

1. Send the report to the receiver as an `Offer(VulnerabilityReport)`.
   [How to Report a Vulnerability](activitypub/activities/report_vulnerability.md#submit-a-report) shows this message.
2. If you have embargo terms, propose them in the report ([EP-04-004](../reference/specs/protocol.md#ep-04-004)).
3. Wait for the decision of the receiver.
   If the receiver opens a case, the receiver is the Case Owner.
   You are a participant with the Reporter role.

### Report to yourself and coordinate

Use this path if you are the correct Case Owner for all of the case.
Two examples are a vendor that finds a vulnerability in its own product, and a coordinator that has a report about many vendors.

1. Send the report to your own actor.
   You get the Reporter role, and you become the Case Owner.
2. Let your system propose the case to your Case Actor Service.
3. Invite each vendor, coordinator, or other actor that the case needs.
   Each actor that accepts becomes a participant ([§12.2 Invitation and Acceptance](../reference/vultron-spec/interactions.md#122-invitation-and-acceptance-n)).

### Report to yourself, invite the vendor, and make a decision later

Use this path if you should be the Case Owner now.
A different participant can possibly coordinate the case later.
An example is a finder that records each vulnerability it finds as a case in its own system.
This finder transfers each case at the time that it selects.

1. Report to yourself, and let your system propose the case, as in the previous path.
2. Invite the vendor, or a different possible Case Owner, to the case.
3. Coordinate the case while you are the correct Case Owner.
4. When a different participant should coordinate the case, do the steps of the next path.

### Transfer the ownership of a case

Use this path if a case is open and a different participant is a better Case Owner.
An example is a vendor that transfers its case to a coordinator when the case includes many vendors.

1. Make sure that the new Case Owner is an active participant of the case.
   An [active participant](../reference/glossary.md#cvd-roles-and-participants) is a participant from the start of the case, or a participant that accepted its invitation.
   It is not removed, and it agrees to the active embargo, if there is one ([CM-10-004](../reference/specs/protocol.md#cm-10-004)).
   If the new Case Owner is not in the case, invite it first.
   Wait until it accepts the invitation.
   When it accepts the invitation, it also agrees to the active embargo ([CM-11-001](../reference/specs/protocol.md#cm-11-001)).
2. Propose the transfer to the Case Manager, and name the new Case Owner.
   The Case Manager refuses a transfer to an actor that is not an active participant ([CM-21-021](../reference/specs/protocol.md#cm-21-021)).
3. Wait for the new Case Owner to accept the transfer.
   It must be an active participant at the time that it accepts ([CM-21-021](../reference/specs/protocol.md#cm-21-021)).

After the transfer, the case keeps its history, its embargo, and its participants.
Only the Case Owner role moves ([CM-21-002](../reference/specs/protocol.md#cm-21-002), [CM-21-003](../reference/specs/protocol.md#cm-21-003)).
You continue to be a participant, and you keep your other roles, for example Reporter or Vendor ([CM-21-008](../reference/specs/protocol.md#cm-21-008), [CM-21-009](../reference/specs/protocol.md#cm-21-009)).
The case record tells each participant about the new Case Owner ([CM-21-007](../reference/specs/protocol.md#cm-21-007)).
[Case Ownership Transfer](../topics/case_lifecycle/ownership_transfer.md) gives the details of each message in the transfer.

---

## Step 3: Select between a report to X and a case that you transfer to X

If you want a different organization, X, to coordinate the case, two paths are possible.
You can send the report to X.
Or, you can make the case yourself and then transfer it to X.
This table compares the decisions that each path gives to you.

| Question | Send a report to X | Make the case, then transfer it to X |
|---|---|---|
| Which actor makes the decision to open a case | X | You |
| Which actor makes the first decisions, for example the embargo terms and the invitations | X, as the Case Owner. If you propose embargo terms, the shorter of your terms and the terms of X becomes active. | You, until X accepts the transfer |
| What occurs if X rejects | X does not open a case. Or, X opens a case and then invalidates or closes the report. If there is a case, X is its Case Owner. | X rejects the transfer. You keep the case, its history, and its participants ([CM-21-012](../reference/specs/protocol.md#cm-21-012)). |
| What you can do after X rejects | Report to yourself and coordinate your own case. If X opened a case for the report, your case is a different case ([CP-05-008](../reference/specs/protocol.md#cp-05-008)). | Propose a transfer to a different participant immediately ([CM-21-014](../reference/specs/protocol.md#cm-21-014)). |

Use this test to select a path.
If these two conditions are true, send the report to X:

- You agree that X makes the decisions.
- If X rejects the report, you do not want to be the Case Owner.

If one condition is not true, make the case first.

It is not an error to make a case only to transfer it later.
A finder that finds many vulnerabilities can record each vulnerability as its own case.
The finder can then transfer each case when it is ready.
The advantage is that the case stays if the new owner rejects it.
The history, the participants, and the embargo stay with the case.

---

## Summary

| Question | Answer |
|---|---|
| What gives the correct path? | The answer to one question: who should be the Case Owner now, and who later? |
| What does it mean to make a case? | You report, possibly to yourself, and you propose the case to a Case Actor Service. The receiver of the report becomes the Case Owner. |
| Does an invitation make an actor the Case Owner? | No. An invitation adds a participant. The Case Owner role moves only by a transfer. |
| Which actor can receive a transfer? | Only an active participant. Invite the new Case Owner first. |
| What stays with the case after a transfer? | The history, the embargo, and the participants. The previous Case Owner continues to be a participant, and it keeps its other roles. |
| When do I send a report directly? | When you agree that the receiver makes the decisions, and you do not want to be the Case Owner if the receiver rejects the report. |

## Further reading

- [A Case Under Vultron](../topics/case_lifecycle/a_case_under_vultron.md) — the Case Owner, what each participant sees, and what an embargo invitation asks
- [Case Ownership Transfer](../topics/case_lifecycle/ownership_transfer.md) — the messages that move the Case Owner role, and why they go through the Case Manager
- [Default Embargoes](../topics/process_models/em/defaults.md) — how a case starts with an embargo, and which terms become active
- [Submit a Report to a Vultron Actor](../tutorials/submit-a-report.md) — how to send a report message to an actor that operates

{% include-markdown "../start/_paths/coordinate-cases/howto__decide_who_owns_a_case.md" %}
