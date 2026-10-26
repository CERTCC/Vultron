---
stakeholder_type: [cvd-practitioner]
level: 300
page_type: explanation
description: >
  When an embargo can be proposed, accepted or rejected, and how long it can reasonably last.
---

# Negotiating Embargoes

{% include-markdown "../../../includes/specification_governs.md" %}

Participants can negotiate a new embargo only while there is still something for it to protect.
This window is the embargo "habitable zone".
It is open until the vulnerability, an exploit for it, or attacks that use it become public knowledge.
The window becomes narrower when a fix is ready, and it is mostly closed when the fix is deployed.

In plain terms:

- **Never** propose or accept a new embargo after the vulnerability is public, an exploit is public, or someone has observed attacks.
  An embargo cannot hide what is already known.
- **Usually do not** after the fix has been deployed, unless there is a specific reason, such as the reasons listed below.
- **Only briefly** after a fix is ready but is neither published nor deployed.
  This short embargo lets Participants prepare for publication or deployment.
- **Otherwise, freely.**

The rules below state the same thing normatively.
Each condition uses the notation of the [CVD Case State model](../cs/cs_model.md).
In this notation, each of six letters records whether an event has occurred:

- the Vendor is aware (*V*)
- a fix is ready (*F*)
- the fix is deployed (*D*)
- the vulnerability is public (*P*)
- an exploit is public (*X*)
- attacks have been observed (*A*)

A capital letter means that the event has occurred.
A lowercase letter means that it has not occurred.
A dot ($\cdot$) means that either value is correct.

!!! note ""

    CVD Participants MUST NOT *propose* or *accept* a new embargo negotiation when any of the following conditions are true:

    1.  Information about the vulnerability is already known to the public (${q^{cs} \in \cdot\cdot\cdot P \cdot\cdot}$).

    2.  An exploit for the vulnerability is publicly available (${q^{cs} \in \cdot\cdot\cdot\cdot X \cdot}$).

    3.  There is evidence that the vulnerability is being actively exploited by adversaries (${q^{cs} \in \cdot\cdot\cdot\cdot\cdot A}$).

!!! note ""

    CVD Participants SHOULD NOT *propose* or *accept* a new embargo negotiation when the fix for a vulnerability has already been deployed ($q^{cs} \in VFDpxa$).

Counterexamples include

- when an embargo is desired to let a downstream Vendor synchronize their fix delivery or deployment
- when a Vendor has deployed a fix but wants to complete their root cause analysis before they release information about the vulnerability.

!!! note ""

    CVD Participants MAY *propose* or *accept* a new embargo when the fix for a vulnerability is ready but has neither been made public nor deployed ($q^{cs} \in VFdpxa$).
    Such an embargo SHOULD be brief and used only to allow Participants to prepare for timely publication or deployment.

!!! note ""

    CVD Participants MAY *propose* or *accept* an embargo in all other case states (${q^{cs} \in \cdot\cdot\cdot pxa}$).

## Asymmetry in Embargo Negotiation

Asymmetry is inherent in the CVD process.
The parties that currently have the vulnerability information decide with whom they will share it.
This asymmetry gives Reporters a small advantage when they first submit a report to another Participant.
[Default Embargoes](defaults.md) describes some ways to reduce this asymmetry, but these ways do not remove it.
For now, it is sufficient to know that the asymmetry exists.

!!! note ""

    Participants MAY *accept* or *reject* any proposed embargo as they see fit.

!!! note ""

    Receivers SHOULD *accept* any embargo proposed by Reporters.

!!! note ""

    Receivers MAY *propose* embargo terms they find more favorable as they see fit.

!!! note ""

    Participants MAY withdraw (*reject*) their own unaccepted *Proposed* embargo.

## Respond Promptly

Timely response to embargo proposals is important.
Explicit acceptance is expected.

!!! note ""

    Participants SHOULD explicitly *accept* or *reject* embargo proposals in a timely manner.
    Outside the two default paths described in [Default Embargoes](defaults.md#embargoes-are-active-at-case-creation), embargo agreement or rejection SHOULD NOT be tacit.

The two default paths are the exception, because they leave nothing open.
On the first path, a Reporter who submits a report without proposing other terms accepts the published default of the Recipient.
On the second path, nobody has proposed or published anything, so the protocol default applies.

!!! note ""
    Participants MAY interpret another Participant's failure to respond to an embargo proposal in a timely manner as a *reject*ion of that proposal.

!!! note ""
    In the absence of an explicit *accept* or *reject* response from a Receiver in a timely manner, the Sender MAY proceed as though the proposal had been rejected: for a revision ($q^{em} \in R \xrightarrow{r} A$, in the [EM shorthand](formal_model.md#em-states)), the terms of the *Active* embargo stay in force.

The protocol reads silence the same way when a Participant is invited to an existing embargo.
Sometimes an invited Participant does not accept or decline before the deadline of the invitation.
The protocol then records that Participant as timed out, not as declined.
This result is the [*pocket veto*](../../behavior_logic/use-cases/embargo-lifecycle.md#inaction-is-an-answer) ([§9.4 Deadlines and the Pocket Veto in the Vultron Protocol Specification](../../../reference/vultron-spec/tracking-models.md#94-deadlines-and-the-pocket-veto)).

## No Embargo means No Embargo

After an embargo negotiation fails the first time, Participants have no further obligations.

!!! note ""

    In a case where the embargo state is _None_ and for which an embargo has been *proposed* and either explicitly or tacitly *rejected*, Participants MAY take any action they choose with the report in question, including immediate publication.

!!! tip "Incentives Matter"

    The clauses "explicitly or tacitly rejected" and "may take any action" above are deliberate.
    They give Participants a reason to be declarative and to negotiate in good faith.

    Suppose that a rejected embargo proposal carried _any_ implied obligation not to publish.
    Then Participants might use delayed or ambiguous responses to put that obligation on others.
    The aim is to prevent this situation: a Participant ignores an embargo proposal but expects the other Participants to stay bound by the proposed-but-inactive terms.
    _Only_ active embargoes impose obligations on Participants.

## Do Not Give Up Too Soon

Even so, the protocol encourages Participants to try again.
This is especially true when no Participant has communicated an explicit rejection, as in the *tacitly rejected* scenario described above.

!!! note ""

    Participants SHOULD make reasonable attempts to retry embargo negotiations when prior proposals have been *reject*ed or otherwise failed to achieve *accept*ance.

## Proposing Terms with a Report

There is no embargo negotiation before a case exists.
A Reporter who wants particular terms attaches a proposed embargo to the report they submit.
When the Recipient creates the case, those terms are weighed against the published default of the Recipient ([ADR-0096: A Protocol Default Embargo Replaces the Pre-Case Phase](../../../adr/0096-protocol-default-embargo.md)).
The shorter of the two takes effect immediately, and the longer becomes a proposed revision.
[Default Embargoes](defaults.md#using-defaults) gives each combination step by step.

The submission of the report is itself a statement of the position of the Reporter.

!!! note ""

    A Sender who submits a report without proposing embargo terms SHALL be construed as accepting the Receiver's published default embargo, where one exists.

Sometimes a Reporter cannot accept the published default of a Recipient.
That Reporter can say so, and propose shorter terms with the report.
The Reporter can also keep the report.

!!! note ""

    Participants MAY withhold a report from a Recipient whose published default embargo they are not prepared to accept.

## Addressing Validation Uncertainty

Participants might prefer to wait before they accept or reject a proposed embargo.
They might want to review the report first, through the validation and (possibly) prioritization processes.
However, other Participants have no obligation to withhold publication of cases that no active embargo covers.
For this reason, we recommend a short embargo until validation is complete.
Participants can then extend the embargo with a revision.

!!! note ""

    Participants MAY use short embargo periods to cover their report validation process, and subsequently revise the embargo terms pending the outcome of their report validation and/or prioritization processes.

!!! note ""

    Participants SHOULD remain flexible in adjusting embargo terms as the case evolves.

## Doing It on the Wire

- [How to Establish an Embargo](../../../howto/activitypub/activities/establish_embargo.md) — propose an embargo, and accept or reject a proposal.
- [How to Revise or Terminate an Embargo](../../../howto/activitypub/activities/manage_embargo.md) — propose a change to an active embargo, and accept or reject it.
