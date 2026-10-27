---
description: >
  Choose between submitting a report, reporting to yourself and running the
  case, and handing a case to someone else, by deciding who should be the Case
  Owner now and later.
stakeholder_type: [cvd-practitioner]
level: 200
page_type: how-to
subject: protocol
---

# How to Decide Who Owns a Case

{% include-markdown "../includes/not_normative.md" %}

Use this guide when you hold a vulnerability and must decide how to bring it into a Coordinated Vulnerability Disclosure (CVD) case under Vultron.
You can submit a report to someone else, report to yourself and run the case, or hand a case you already run to someone better placed.
One question decides between them: who should be the [Case Owner](../reference/glossary.md#cvd-roles-and-participants), now and later?
You finish with a chosen path and the steps to take it.

---

## Prerequisites

- You know what a case is, who owns it, and who keeps its record.
  [A Case Under Vultron](../topics/case_lifecycle/a_case_under_vultron.md) covers this.
- You know what an [embargo](../topics/process_models/em/principles.md) asks of the participants that agree to it.
- Your organization runs, or has access to, a system that sends and receives Vultron messages.

---

## Step 1: Learn what each choice commits you to

Four facts about the protocol decide what each path gives you.
Read them before you choose.

**Creating a case means reporting and proposing.**
No participant creates a case directly.
The actor that receives a report, which can be you, proposes a case to a [Case Actor Service](../reference/glossary.md#cvd-roles-and-participants).
The service creates the case and keeps its history as the case's [Case Manager](../topics/case_lifecycle/case_manager_and_ledger.md).
It makes the report's receiver the Case Owner and adds the Reporter as a participant ([CP-09-001](../reference/specs/protocol.md#cp-09-001), [CP-09-002](../reference/specs/protocol.md#cp-09-002), [CM-22-001](../reference/specs/protocol.md#cm-22-001)).
So whoever receives the report owns the case.

**An invitation adds a participant, not an owner.**
When the Case Owner invites an actor, that actor joins with the roles the invitation names ([§12.2 Invitation and Acceptance](../reference/vultron-spec/interactions.md#122-invitation-and-acceptance-n)).
A case has one owner at a time, and the Case Owner role moves only through an [ownership transfer](../topics/case_lifecycle/ownership_transfer.md) ([CM-21-001](../reference/specs/protocol.md#cm-21-001), [CM-21-002](../reference/specs/protocol.md#cm-21-002)).
If you create a case and invite the vendor, you still make the case's decisions.

**Anyone who reports is the Reporter.**
The protocol has no finder role ([ADR-0078](../adr/0078-retire-finder-role.md)).
A [finder](../reference/glossary.md#cvd-roles-and-participants), a vendor that found a vulnerability in its own product, and a coordinator that holds a report all take the [Reporter](../reference/glossary.md#cvd-roles-and-participants) role when they report it.
Who found the vulnerability is recorded in the report, not as a role.

**A submitted report agrees to the case's embargo.**
When a case is created from your report, you are seated as a signatory to any embargo already active ([CM-14-005](../reference/specs/protocol.md#cm-14-005)).
You can propose your own embargo terms in the report ([EP-04-004](../reference/specs/protocol.md#ep-04-004)).
If the receiver also has default terms, the shorter embargo takes effect and the longer becomes a proposed revision ([EP-04-003](../reference/specs/protocol.md#ep-04-003), [Default Embargoes](../topics/process_models/em/defaults.md)).

---

## Step 2: Choose a path

The four paths below run from lightest to heaviest.
Take the first one whose condition fits you.

| Path | Choose it when | Who is the Case Owner |
|---|---|---|
| Submit a report | The receiver should own the case and decide what happens | The receiver |
| Report to yourself and coordinate | You should own the case for its whole life | You |
| Report to yourself, invite the vendor, decide later | You should own the case now, and may hand it on later | You, until you transfer it |
| Transfer ownership of an existing case | A case exists and another participant should now run it | The participant you transfer it to |

### Submit a report

Choose this path when you are content for the receiver to decide whether a case exists and how it runs.
This is the usual path for a finder that reports to a vendor or a coordinator.

1. Send the report to the receiver as an `Offer(VulnerabilityReport)`.
   [Submit a Report to a Vultron Actor](../tutorials/submit-a-report.md) shows the message.
2. Optionally, propose embargo terms in the report ([EP-04-004](../reference/specs/protocol.md#ep-04-004)).
3. Wait for the receiver's decision.
   If it opens a case, it is the Case Owner and you join as the Reporter.

### Report to yourself and coordinate

Choose this path when you are the right owner for the whole case.
Examples are a vendor that found a vulnerability in its own product, and a coordinator that holds a report affecting several vendors.

1. Address the report to your own actor.
   You hold the Reporter role and become the Case Owner.
2. Let your system propose the case to your Case Actor Service.
3. Invite each vendor, coordinator, or other party the case needs.
   Each one joins as a participant ([§12.2 Invitation and Acceptance](../reference/vultron-spec/interactions.md#122-invitation-and-acceptance-n)).

### Report to yourself, invite the vendor, decide later

Choose this path when you should own the case now but may want someone else to run it later.
An example is a finder that tracks every finding in its own system and hands coordination on when it chooses.

1. Report to yourself and let your system propose the case, as in the previous path.
2. Invite the vendor, or any other future owner, into the case.
3. Run the case while you are the right owner.
4. When you decide another participant should run it, take the next path.

### Transfer ownership of an existing case

Choose this path when a case exists and another participant is better placed to run it.
An example is a vendor that hands its case to a coordinator once it involves several vendors.

1. Make sure the future owner is an active participant of the case.
   An [active participant](../reference/glossary.md#cvd-roles-and-participants) has joined, has not been removed, and has agreed to the active embargo while one is in force ([CM-10-004](../reference/specs/protocol.md#cm-10-004)).
   If the future owner is not in the case, invite it first and wait until it accepts.
   Accepting the invitation agrees to the active embargo ([CM-11-001](../reference/specs/protocol.md#cm-11-001)).
2. Propose the transfer to the Case Manager, naming the future owner.
   The Case Manager refuses a transfer to anyone who is not an active participant ([CM-21-021](../reference/specs/protocol.md#cm-21-021)).
3. Wait for the future owner to accept.
   It must still be an active participant when it accepts ([CM-21-021](../reference/specs/protocol.md#cm-21-021)).

When the transfer completes, the case keeps its history, its embargo, and its participants.
Only the Case Owner role moves ([CM-21-002](../reference/specs/protocol.md#cm-21-002), [CM-21-003](../reference/specs/protocol.md#cm-21-003)).
You stay a participant, and you keep your other roles, such as Reporter or Vendor ([CM-21-008](../reference/specs/protocol.md#cm-21-008), [CM-21-009](../reference/specs/protocol.md#cm-21-009)).
Every participant learns of the new owner from the case's record ([CM-21-007](../reference/specs/protocol.md#cm-21-007)).
[Case Ownership Transfer](../topics/case_lifecycle/ownership_transfer.md) explains each message in the exchange.

---

## Step 3: Decide between submitting to X and creating the case for X

When you expect another organization, X, to run the case, two paths can get it there.
You can submit the report to X, or create the case yourself and then transfer it to X.
The table below compares what each one leaves in your hands.

| Question | Submit a report to X | Create the case, then transfer it to X |
|---|---|---|
| Who decides whether a case exists | X | You |
| Who makes the early decisions, such as embargo terms and invitations | X, as the Case Owner, with your proposed embargo terms weighed against its own | You, until X accepts the transfer |
| What happens if X declines | X invalidates or closes your report, or opens no case, and any case that exists is X's, not yours | X rejects the transfer, and you keep the case, its history and its participants ([CM-21-012](../reference/specs/protocol.md#cm-21-012)) |
| What you can do next if X declines | Report to yourself and run a case of your own ([CP-05-008](../reference/specs/protocol.md#cp-05-008)) | Propose a transfer to another participant at once ([CM-21-014](../reference/specs/protocol.md#cm-21-014)) |

Apply this test to choose.
Submit directly when you are content for X to decide, and you would not want to own the case if X declines.
Otherwise, create the case first.

Creating a case only to transfer it is not a mistake in itself.
A finder that handles many vulnerabilities can track every finding as its own case and hand coordination on when it chooses.
What it gains is a case that survives a decline: the history, the participants and the embargo stay with it.

---

## Summary

| Question | Answer |
|---|---|
| What decides the path? | Who should be the Case Owner, now and later. |
| What does creating a case involve? | Reporting, possibly to yourself, and proposing the case to a Case Actor Service. The receiver of the report becomes the Case Owner. |
| Does an invitation make someone an owner? | No. It adds a participant. Ownership moves only by a transfer. |
| Who can receive a transfer? | Only an active participant. Invite the future owner first. |
| What carries over in a transfer? | The history, the embargo and the participants. The previous owner stays a participant with its other roles. |
| When should I submit directly? | When you are content for the receiver to decide, and would not want to own the case if it declines. |

## Further reading

- [A Case Under Vultron](../topics/case_lifecycle/a_case_under_vultron.md) — who owns a case, what each participant sees, and what an embargo invitation asks
- [Case Ownership Transfer](../topics/case_lifecycle/ownership_transfer.md) — the messages that move the Case Owner role, and why they go through the Case Manager
- [Default Embargoes](../topics/process_models/em/defaults.md) — how a case starts under an embargo, and which terms win
- [Submit a Report to a Vultron Actor](../tutorials/submit-a-report.md) — the report message, sent to a running actor

{% include-markdown "../start/_paths/coordinate-cases/howto__decide_who_owns_a_case.md" %}
