---
description: >
  Choose between submitting a report, reporting to yourself and coordinating
  the case, and transferring a case to someone else. One question decides it:
  who should be the Case Owner now, and who later?
stakeholder_type: [cvd-practitioner]
level: 200
page_type: how-to
subject: protocol
---

# How to Decide Who Owns a Case

{% include-markdown "../includes/not_normative.md" %}

Use this guide when you have a vulnerability and must start a Coordinated Vulnerability Disclosure (CVD) case for it under Vultron.
You can submit a report to another organization, such as a vendor or a coordinator.
You can also report to yourself and coordinate the case.
If you already own a case, you can transfer it to a participant that is better placed to coordinate it.
One question decides between these paths: who should be the [Case Owner](../reference/glossary.md#cvd-roles-and-participants) now, and who later?

---

## Prerequisites

- You know what a case is, which participant owns it, and which participant keeps its record.
  [A Case Under Vultron](../topics/case_lifecycle/a_case_under_vultron.md) covers this.
- You know what an [embargo](../topics/process_models/em/principles.md) asks of the participants that agree to it.
- Your organization operates a system that sends and receives Vultron messages, or can use one.

---

## Step 1: Know the five rules behind each path

Five protocol rules decide what each path gives you.
Read them before you choose a path.

**The receiver of a report creates the case and owns it.**
No actor creates a case without a report.
Any actor that receives a report can create a case for it: a vendor, a coordinator, or you, if you report to yourself.
The receiver becomes the Case Owner, and the Reporter becomes a participant ([CM-14-008](../reference/specs/protocol.md#cm-14-008), [CM-14-009](../reference/specs/protocol.md#cm-14-009), [CM-14-012](../reference/specs/protocol.md#cm-14-012)).
So the actor that receives the report owns the case.

**The Case Owner holds the Case Manager role, or delegates it.**
Each case has a [Case Manager](../topics/case_lifecycle/case_manager_and_ledger.md), which keeps the history of the case and sends each change to the participants.
The Case Owner can hold this role itself.
The Case Owner can also delegate it to a different actor, for example a coordinator that hosts cases for others ([§10.3 Case Bootstrap and the Trust Root](../reference/vultron-spec/interactions.md#103-case-bootstrap-and-the-trust-root), [CBT-01-001](../reference/specs/protocol.md#cbt-01-001)).
When it delegates, the delegate creates the case, and the receiver of the report is still its Case Owner ([CP-09-001](../reference/specs/protocol.md#cp-09-001), [CBT-01-003](../reference/specs/protocol.md#cbt-01-003)).
The rest of this guide is the same in both cases.

!!! note "Delegation in the reference implementation"

    The Vultron reference implementation always delegates the Case Manager role.
    The receiver proposes the case to a [Case Actor Service](../reference/glossary.md#cvd-roles-and-participants), which starts a separate Case Actor for the case.
    The protocol does not require this.

**An invitation adds a participant, not an owner.**
When the Case Owner invites an actor, that actor becomes a participant with the roles that the invitation names ([§12.2 Invitation and Acceptance](../reference/vultron-spec/interactions.md#122-invitation-and-acceptance-n)).
A case has only one Case Owner at a time ([CM-21-001](../reference/specs/protocol.md#cm-21-001)).
The Case Owner role moves to another participant only by an [ownership transfer](../topics/case_lifecycle/ownership_transfer.md) ([CM-21-002](../reference/specs/protocol.md#cm-21-002)).
The Case Manager refuses any other offer of the Case Owner role ([CM-33-003](../reference/specs/protocol.md#cm-33-003)).
If you create a case and invite a vendor, you still make the decisions for the case.

**The actor that reports is the Reporter.**
The protocol has no finder role ([ADR-0078](../adr/0078-retire-finder-role.md)).
The actor that reports a vulnerability holds the [Reporter](../reference/glossary.md#cvd-roles-and-participants) role.
That actor can be a [finder](../reference/glossary.md#cvd-roles-and-participants), a vendor that found a vulnerability in its own product, or a coordinator.
The report records who found the vulnerability, and the role does not.

**A submitted report agrees to the embargo of the case.**
When a case is created from your report, you become a signatory to any active embargo ([CM-14-005](../reference/specs/protocol.md#cm-14-005)).
You can propose your own embargo terms in the report ([EP-04-004](../reference/specs/protocol.md#ep-04-004)).
If the receiver also has default terms, the shorter embargo becomes active ([EP-04-003](../reference/specs/protocol.md#ep-04-003), [Default Embargoes](../topics/process_models/em/defaults.md)).
The longer one should become a proposed revision.

---

## Step 2: Choose a path

The four paths below go from the least work to the most work.
Take the first path whose condition is true for you.

| Path | Use it when | Who is the Case Owner |
|---|---|---|
| Submit a report | The receiver should own the case and make its decisions | The receiver |
| Report to yourself and coordinate | You should own the case for its whole life | You |
| Report to yourself, invite the others, and decide later | You should own the case now, and another participant may own it later | You, until you transfer the case |
| Transfer ownership of an existing case | A case exists, and another participant should now coordinate it | The participant that accepts the transfer |

### Submit a report

Use this path if you are content for the receiver to decide whether a case exists and how it runs.
This is the usual path for a finder that reports to a vendor or a coordinator.

1. Send the report to the receiver as an `Offer(VulnerabilityReport)`.
   [How to Report a Vulnerability](activitypub/activities/report_vulnerability.md#submit-a-report) shows this message.
2. If you have embargo terms, propose them in the report ([EP-04-004](../reference/specs/protocol.md#ep-04-004)).
3. Wait for the receiver to decide.
   If the receiver creates a case, the receiver is the Case Owner.
   You are a participant with the Reporter role.

### Report to yourself and coordinate

Use this path if you are the right owner for the whole case.
Two examples are a vendor that found a vulnerability in its own product, and a coordinator that holds a report affecting several vendors.

1. Send the report to your own actor.
   You hold the Reporter role, and you become the Case Owner.
2. Create the case.
   Hold the Case Manager role yourself, or delegate it to an actor that you choose.
3. Invite each vendor, coordinator, or other actor that the case needs.
   Each actor that accepts becomes a participant ([§12.2 Invitation and Acceptance](../reference/vultron-spec/interactions.md#122-invitation-and-acceptance-n)).

### Report to yourself, invite the others, and decide later

Use this path if you should own the case now.
Another participant may be a better owner later.
An example is a finder that records each vulnerability it finds as a case in its own system.
That finder transfers each case when it chooses.

1. Report to yourself and create the case, as in the previous path.
2. Invite the other parties that the case needs, including any possible future owner.
   A future owner can be a vendor, a coordinator, or any other participant.
3. Coordinate the case while you are the right owner.
4. When another participant should coordinate the case, take the next path.

### Transfer ownership of an existing case

Use this path if a case exists and another participant is better placed to coordinate it.
An example is a vendor that transfers its case to a coordinator when the case comes to include several vendors.

1. Make sure that the new owner is an active participant of the case.
   An [active participant](../reference/glossary.md#cvd-roles-and-participants) was in the case from its start, or accepted an invitation to it.
   It has not been removed, and it agrees to the active embargo, if there is one ([CM-10-004](../reference/specs/protocol.md#cm-10-004)).
   If the new owner is not in the case, invite it first.
   Wait until it accepts the invitation.
   When it accepts, it also agrees to the active embargo ([CM-11-001](../reference/specs/protocol.md#cm-11-001)).
2. Propose the transfer to the Case Manager, which can be your own system, and name the new owner ([CM-21-005](../reference/specs/protocol.md#cm-21-005)).
   The Case Manager refuses a transfer to an actor that is not an active participant ([CM-21-021](../reference/specs/protocol.md#cm-21-021)).
3. Wait for the new owner to accept the transfer.
   It must be an active participant when it accepts ([CM-21-021](../reference/specs/protocol.md#cm-21-021)).

After the transfer, the case keeps its history, its embargo, and its participants.
Only the Case Owner role moves ([CM-21-002](../reference/specs/protocol.md#cm-21-002), [CM-21-003](../reference/specs/protocol.md#cm-21-003)).
You stay a participant, and you keep your other roles, for example Reporter or Vendor ([CM-21-008](../reference/specs/protocol.md#cm-21-008), [CM-21-009](../reference/specs/protocol.md#cm-21-009)).
The Case Manager tells each participant about the new owner ([CM-21-007](../reference/specs/protocol.md#cm-21-007)).

The Case Manager role does not move with the Case Owner role.
If you held both roles, you still hold the Case Manager role after the transfer.
The protocol does not yet say how that role moves to another actor ([§12.1 Role Assignment](../reference/vultron-spec/interactions.md#121-role-assignment-n), [Open questions: cases and participants](../topics/future_work/open_questions.md#cases-and-participants)).
[Case Ownership Transfer](../topics/case_lifecycle/ownership_transfer.md) describes each message in the transfer.

---

## Step 3: Choose between submitting to X and creating the case for X

If you want another organization, X, to coordinate the case, two paths can get it there.
You can submit the report to X.
Or you can create the case yourself and then transfer it to X.
The table below compares what each path leaves in your hands.

| Question | Submit a report to X | Create the case, then transfer it to X |
|---|---|---|
| Who decides whether a case exists | X | You |
| Who makes the early decisions, such as the embargo terms and the invitations | X, as the Case Owner. Your proposed embargo terms apply as Step 1 describes. | You, until X accepts the transfer |
| What happens if X declines | X creates no case, or creates one and then invalidates or closes the report. Any case that exists is owned by X, not by you. | X rejects the transfer. You keep the case, its history, and its participants ([CM-21-012](../reference/specs/protocol.md#cm-21-012)). |
| What you can do next if X declines | Report to yourself and create a case of your own. It is separate from any case that X created. | Propose a transfer to another participant at once ([CM-21-014](../reference/specs/protocol.md#cm-21-014)). |

Use this test to choose.
If both of these conditions are true, submit the report to X:

- You are content for X to decide.
- If X declines, you do not want to own the case.

If either condition is false, create the case first.

Creating a case only to transfer it is not a mistake.
A finder that finds many vulnerabilities can record each one as its own case.
The finder can then transfer each case when it is ready.
The benefit is that the case outlives a decline: the history, the participants, and the embargo stay with it.

---

## Summary

| Question | Answer |
|---|---|
| What decides the path? | Who should be the Case Owner, now and later. |
| Who creates a case? | The actor that receives the report, which can be you. That actor becomes the Case Owner. |
| Who is the Case Manager? | The Case Owner, or an actor that the Case Owner delegates the role to. |
| Does an invitation make someone an owner? | No. It adds a participant. Ownership moves only by a transfer. |
| Who can receive a transfer? | Only an active participant. Invite the future owner first. |
| What stays with the case after a transfer? | The history, the embargo, and the participants. The previous owner stays a participant and keeps its other roles. |
| When should I submit directly? | When you are content for the receiver to decide, and you would not want to own the case if it declines. |

## Further reading

- [A Case Under Vultron](../topics/case_lifecycle/a_case_under_vultron.md) — who owns a case, what each participant sees, and what an embargo invitation asks
- [Case Ownership Transfer](../topics/case_lifecycle/ownership_transfer.md) — the messages that move the Case Owner role, and why they go through the Case Manager
- [Default Embargoes](../topics/process_models/em/defaults.md) — how a case starts under an embargo, and which terms become active
- [Submit a Report to a Vultron Actor](../tutorials/submit-a-report.md) — the report message, sent to a running actor in the reference implementation

{% include-markdown "../start/_paths/coordinate-cases/howto__decide_who_owns_a_case.md" %}
