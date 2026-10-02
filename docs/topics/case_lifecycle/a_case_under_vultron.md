---
description: >
  What a Coordinated Vulnerability Disclosure case looks like from a
  participant's seat under Vultron: who owns it, what each participant sees
  and controls, and what an embargo invitation asks of them.
stakeholder_type: [cvd-practitioner]
level: 200
---

# A Case Under Vultron

This page explains what a Coordinated Vulnerability Disclosure (CVD) case looks like from your seat when the organizations in it coordinate through Vultron.
It covers who owns the case, who keeps its record, what you see of it, how your own part of it moves, and what an embargo invitation asks of you.
It is written for people who handle vulnerability reports and coordinate cases, and it stops short of the message formats and the record-keeping machinery, which have their own pages.
If you have not yet read [What Is Vultron?](../background/what-is-vultron.md), start there.

---

## Your seat in the case

A **case** is the coordination context around one vulnerability: the participants, the shared state, the messages they exchange, and any embargo agreement ([§2.1 Actors, Participants and Cases in the Vultron Protocol Specification](../../reference/vultron-spec/introduction.md#21-actors-participants-and-cases)).
You take part in it as a **participant**, through the system your organization runs.
Vultron does not replace that system.
It gives it a way to exchange the case with the systems your partners run, in the way that mail servers exchange mail.

What you do in a case is described by the **roles** you hold in it.
The roles are the ones the CVD process already uses ([§2.2 Roles](../../reference/vultron-spec/introduction.md#22-roles), [glossary](../../reference/glossary.md#cvd-roles-and-participants)).

| Role | What it means in a case |
|---|---|
| Reporter | You submitted the report that the case is about |
| Vendor | You produce the affected product and are responsible for a fix |
| Coordinator | You facilitate the coordination without owning a fix |
| Deployer | You operate systems that need the fix applied |
| CVE Numbering Authority (CNA) | You assign Common Vulnerabilities and Exposures (CVE) IDs directly |
| Observer | You follow the case and are bound by its embargo, with no fix obligations |

Roles are not exclusive.
A vendor that finds a vulnerability in its own product is both Reporter and Vendor.
Roles also belong to the case, not to your organization: you may be the Reporter in one case and a Vendor in the next.
Vultron records who holds which role, so every participant reads the same answer.
Roles are assigned through the case, never claimed: you do not become a Coordinator by saying so ([§11.1 Role Assignment](../../reference/vultron-spec/interactions.md#111-role-assignment-n)).

---

## Who owns the case, and who keeps its record

Two further roles describe authority over the case itself rather than a part in the disclosure.

The **Case Owner** is the participant whose disclosure decision the case exists to serve.
It decides who is admitted to the case, which roles they hold, and whether embargo terms are accepted or torn down ([§2.2 Roles](../../reference/vultron-spec/introduction.md#22-roles)).
When you open a case, you are its owner.
Ownership can move: a vendor that opened a case can hand it to a coordinator, and every participant learns who decides for the case now ([Case Ownership Transfer](ownership_transfer.md)).

The **Case Manager** keeps the case's authoritative history and passes case messages between participants, acting on the Case Owner's behalf ([The CASE_MANAGER and the Case Ledger](case_manager_and_ledger.md)).
It is the one participant that writes the shared record of the case.
Every other participant holds a copy of that record, and the Case Manager sends each accepted change to all of them.
In practice the Case Owner's own system usually holds this role, and the owner may delegate it, for example to a coordinator that hosts cases for others ([§11.1 Role Assignment](../../reference/vultron-spec/interactions.md#111-role-assignment-n)).

The practical consequence is the one that matters to a practitioner: there is exactly one history of what happened in the case, and everyone in the case holds the same copy of it.
No participant reconciles competing versions, and nobody edits the record directly, not even the organization that opened the case.

This is not a central clearinghouse.
The Case Manager role is held per case, so a different case can route through a different organization, and no service sees every case ([§3.2 What a Deployment Looks Like](../../reference/vultron-spec/introduction.md#32-what-a-deployment-looks-like)).

---

## What you see

Your system holds its own copy of the case, assembled from the messages that have reached it ([§3.1 Coordination Model](../../reference/vultron-spec/introduction.md#31-coordination-model)).
Because every accepted change comes from the Case Manager and goes to every participant, your copy and your partners' copies show the same case history, once the messages have arrived.

The table below lists what that copy tells you, whose state each item is, and who can change it.

| What you see | Whose state it is | Who changes it |
|---|---|---|
| Who the participants are, and their roles | The case's | The Case Owner, through the Case Manager |
| Where you stand on the report: received, valid, accepted, closed | Yours | Only you |
| Where each other participant stands on the report | Theirs | Only that participant |
| Whether a fix is ready or deployed, per vendor or deployer | That participant's | That participant |
| Whether the case has an embargo, and its terms | The case's | The Case Owner, through the Case Manager |
| Whether you have agreed to the current embargo terms | Yours | You, by accepting or declining |
| What is publicly known: the vulnerability, an exploit, attacks | The case's | Any participant may report it; the Case Manager records it |

Every message in a case states that something has already happened.
An acceptance says *we accepted this report*; it does not instruct you to accept it too ([§3.2 What a Deployment Looks Like](../../reference/vultron-spec/introduction.md#32-what-a-deployment-looks-like)).
The one exception is a proposal, such as an embargo invitation, which asks for a decision.

Two things stay as they are today.
You still talk to your partners by mail, phone, or a shared channel; the protocol carries only the traffic that changes the case ([§3.2 What a Deployment Looks Like](../../reference/vultron-spec/introduction.md#32-what-a-deployment-looks-like)).
And you see nothing of a case you have not joined: an invitation carries a minimal description of the case, and the vulnerability detail follows only after you accept ([§11.2 Invitation and Acceptance](../../reference/vultron-spec/interactions.md#112-invitation-and-acceptance-n)).

---

## How your part of the case moves

Each participant handles the report in its own way, and Vultron does not dictate how.
It carries the outcome: where you now stand on the report.
Those positions are the Report Management (RM) states, and every participant has its own ([Report Management Process Model](../process_models/rm/index.md)).

{% include-markdown "../../reference/vultron-spec/includes/_rm-states-table.md" %}

Only you move your own RM state.
When you move it, your system tells the other participants, and their copies of the case update.
A vendor learns that a coordinator has accepted a report from the coordinator's message, not by asking.

Nothing here decides for you.
Whether a report is credible, how urgent it is, and when an advisory is ready to publish remain your organization's judgment calls; the protocol only records the answers.
The [Capability Model](../capability_model/index.md) lists every such decision and where your own process supplies it.

---

## What an embargo invitation asks of you

{% include-markdown "../process_models/em/_embargo_defn.md" %}

A case has at most one embargo at a time, and its state belongs to the case as a whole ([Embargo Management Process Model](../process_models/em/index.md)).
Whether *you* have agreed to the current terms is a separate question, recorded per participant as [embargo consent](../behavior_logic/use-cases/embargo-lifecycle.md), because a participant that joined late or declined is in the case without being bound ([§9 Participant Embargo Consent (PEC) State Machine](../../reference/vultron-spec/tracking-models.md#9-participant-embargo-consent-pec-state-machine-n)).

An embargo invitation reaches you in one of two ways.
If you are invited to a case that already has an embargo, the invitation states the terms you would be agreeing to, and accepting it both seats you in the case and records your consent ([§11.2 Invitation and Acceptance](../../reference/vultron-spec/interactions.md#112-invitation-and-acceptance-n)).
If you are already in a case and a participant proposes an embargo or a change to one, you receive the proposed terms and are asked to answer.

In either form, the invitation asks for one decision, and the table below shows what follows from each answer.

| Your answer | What follows |
|---|---|
| Accept | You are a signatory to the terms. You are expected not to disclose the vulnerability to anyone outside the case until the embargo ends ([Embargo Principles](../process_models/em/principles.md)). |
| Decline | You are not bound. You still receive the negotiation traffic, so you can accept later terms, but embargoed case content is withheld from you ([§9.5 Embargo Traffic Reaches Non-Signatories](../../reference/vultron-spec/tracking-models.md#95-embargo-traffic-reaches-non-signatories), [§9.7 Gating Full Case Delivery](../../reference/vultron-spec/tracking-models.md#97-gating-full-case-delivery)). |
| No answer by the deadline | Treated as declined ([§9.4 Deadlines and the Pocket Veto](../../reference/vultron-spec/tracking-models.md#94-deadlines-and-the-pocket-veto)). |
| Propose different terms | The shortest proposed embargo is taken as accepted and the longer one as a proposed revision, so the case has an embargo while you negotiate ([Default Embargoes](../process_models/em/defaults.md)). |

Three things happen without anyone asking you.

| Event | What it means for you |
|---|---|
| A case begins already under embargo | A report recipient that publishes a default embargo period in its vulnerability disclosure policy has made a standing proposal, and a Reporter who submits without proposing other terms has accepted it ([Default Embargoes](../process_models/em/defaults.md)). Publishing your own default is the most useful thing your organization can do before its first case. |
| The terms are revised | A proposed revision changes nothing for you: the old terms stay in force and so does your consent to them. When the case owner activates the revision, you are carried over if it ends no later than the terms you accepted; if it ends later and you have not accepted it, your consent lapses until you do. |
| The vulnerability, an exploit for it, or attacks using it become public | The embargo ends for everyone, and every participant's consent resets ([Early Termination](../process_models/em/early_termination.md)). Be prepared for this before you accept. |

Who else to bring into an embargoed case, and when, is the subject of [Adding Participants to an Embargoed Case](../process_models/em/working_with_others.md).
The rules on when a new embargo may still be proposed are in [Negotiating Embargoes](../process_models/em/negotiating.md).

---

## When the case ends for you

You close your own report when your work on it is done: the fix is shipped, the advisory is published, or the report was not valid for you.
Closing is yours alone, and the case can continue for other participants after you close.
Publication follows the embargo, not the other way round: once the embargo ends, no restriction on publishing remains.
What a good outcome looks like across the whole case, and how the roles pull toward it, is the subject of [What Does *Success* Mean in CVD?](../background/cvd_success.md).

---

## Summary

| Question | Answer |
|---|---|
| Who owns the case? | The Case Owner, whose disclosure decision the case serves. Ownership can be transferred. |
| Who keeps the record? | The Case Manager, the one participant that writes the shared history and sends every change to everyone. |
| What do I see? | The same case history as every other participant: who is in the case, where each stands on the report, the embargo, and what is public. |
| What do I control? | Your own report handling, your own fix status, and your own answer to embargo terms. |
| What does an embargo invitation ask? | One decision: accept the stated terms, decline them, or propose others. Silence counts as declining. |
| What decides for me? | Nothing. Validity, priority, embargo terms, and publication readiness stay your organization's calls. |

## Further reading

- [How to Adopt Vultron in Your CVD Program](../../howto/adopt_vultron.md) — the steps from this page to a program that coordinates through the protocol
- [Embargo Principles](../process_models/em/principles.md) — what it means to cooperate with an embargo
- [Default Embargoes](../process_models/em/defaults.md) — declaring a default in your disclosure policy, and why a case starts under one
- [Report Management Process Model](../process_models/rm/index.md) — the report states in full
- [Capability Model](../capability_model/index.md) — every decision the protocol leaves to your organization
- [The Case Model](case_model.md) and [The CASE_MANAGER and the Case Ledger](case_manager_and_ledger.md) — the objects and the record-keeping behind this page, written for the people who build the systems
- [Vultron Protocol Specification, §3 Protocol Overview](../../reference/vultron-spec/introduction.md#3-protocol-overview-i) — the coordination model in normative terms
