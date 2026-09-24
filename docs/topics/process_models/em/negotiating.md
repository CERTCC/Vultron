---
stakeholder_type: [cvd-practitioner]
level: 300
---

# Negotiating Embargoes

{% include-markdown "../../../includes/normative.md" %}

A new embargo can only be negotiated while there is still something for it to protect.
That window, the embargo "habitable zone", is open until the vulnerability, an exploit for it, or attacks using it become public knowledge.
It narrows once a fix is ready, and has mostly closed once the fix is deployed.

In plain terms:

- **Never** propose or accept a new embargo once the vulnerability is public, an exploit is public, or attacks have been observed.
  An embargo cannot hide what is already known.
- **Usually don't** once the fix has been deployed, unless there is a specific reason, such as those listed below.
- **Only briefly** once a fix is ready but neither published nor deployed, to let Participants prepare for publication or deployment.
- **Otherwise, freely.**

The rules below state the same thing normatively.
Each condition is given in the notation of the [CVD Case State model](../cs/cs_model.md), where each of six letters records whether an event has happened: the Vendor is aware (*V*), a fix is ready (*F*), the fix is deployed (*D*), the vulnerability is public (*P*), an exploit is public (*X*), and attacks have been observed (*A*).
A capital letter means the event has happened, a lowercase letter that it has not, and a dot ($\cdot$) that either will do.

!!! note ""

    CVD Participants MUST NOT *propose* or *accept* a new embargo negotiation when any of the following conditions are true:

    1.  Information about the vulnerability is already known to the public (${q^{cs} \in \cdot\cdot\cdot P \cdot\cdot}$).

    2.  An exploit for the vulnerability is publicly available (${q^{cs} \in \cdot\cdot\cdot\cdot X \cdot}$).

    3.  There is evidence that the vulnerability is being actively exploited by adversaries (${q^{cs} \in \cdot\cdot\cdot\cdot\cdot A}$).

!!! note ""

    CVD Participants SHOULD NOT *propose* or *accept* a new embargo negotiation when the fix for a vulnerability has already been deployed ($q^{cs} \in VFDpxa$).

Counterexamples include

- when an embargo is desired to allow for a downstream Vendor to synchronize their fix delivery or deployment
- when a Vendor has deployed a fix but wants to complete their root cause analysis prior to releasing information about the vulnerability.

!!! note ""

    CVD Participants MAY *propose* or *accept* a new embargo when the fix for a vulnerability is ready but has neither been made public nor deployed ($q^{cs} \in VFdpxa$).
    Such an embargo SHOULD be brief and used only to allow Participants to prepare for timely publication or deployment.

!!! note ""

    CVD Participants MAY *propose* or *accept* an embargo in all other case states (${q^{cs} \in \cdot\cdot\cdot pxa}$).

## Asymmetry in Embargo Negotiation

Asymmetry is inherent in the CVD process because those who currently have the vulnerability information get to decide with whom they will share it.
This asymmetry puts Reporters at somewhat of an advantage when it comes to the initial report submission to another Participant.
[Default Embargoes](defaults.md) describes some ways to reduce, though not remove, this asymmetry; for now it is enough to acknowledge that it exists.

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

The two default paths are the exception because nothing is left open on them: a Reporter who submits a report without proposing other terms accepts the Recipient's published default, and where nobody has proposed or published anything, the protocol default applies.

!!! note ""
    Participants MAY interpret another Participant's failure to respond to an embargo proposal in a timely manner as a *reject*ion of that proposal.

!!! note ""
    In the absence of an explicit *accept* or *reject* response from a Receiver in a timely manner, the Sender MAY proceed as though the proposal had been rejected: for a revision ($q^{em} \in R \xrightarrow{r} A$, in the [EM shorthand](formal_model.md#em-states)), the terms of the *Active* embargo stay in force.

The protocol reads silence the same way when a Participant is invited to an existing embargo.
A Participant who neither accepts nor declines before the invitation's deadline is recorded as having declined, the [*pocket veto*](../../behavior_logic/use-cases/embargo-lifecycle.md#inaction-is-an-answer) ([§9.4 of the Vultron Protocol Specification](../../../reference/vultron-spec/index.md#94-deadlines-and-the-pocket-veto)).

## No Embargo means No Embargo

Once an embargo negotiation has failed the first time, Participants have no further obligations.

!!! note ""

    In a case where the embargo state is _None_ and for which an embargo has been *proposed* and either explicitly or tacitly *rejected*, Participants MAY take any action they choose with the report in question, including immediate publication.

!!! tip "Incentives Matter"

    The clauses "explicitly or tacitly rejected" and "may take any action" above are deliberate: they give Participants a reason to be declarative and to negotiate in good faith.
    Were a rejected embargo proposal to carry _any_ implied obligation to refrain from publication, Participants might be motivated to use delayed or ambiguous responses to impose that obligation on others.
    The aim is to avoid a Participant ignoring an embargo proposal while expecting the other Participants to stay bound by the proposed-but-inactive terms.
    _Only_ active embargoes impose obligations on Participants.

## Don't Give Up Too Soon

The above notwithstanding, Participants are encouraged to try again, especially when no explicit rejection has been communicated (i.e., in the *tacitly rejected* scenario described above).

!!! note ""

    Participants SHOULD make reasonable attempts to retry embargo negotiations when prior proposals have been *reject*ed or otherwise failed to achieve *accept*ance.

## Proposing Terms with a Report

There is no embargo negotiation before a case exists.
A Reporter who wants particular terms attaches a proposed embargo to the report they submit, and those terms are weighed against the Recipient's published default when the Recipient creates the case ([ADR-0096: A Protocol Default Embargo Replaces the Pre-Case Phase](../../../adr/0096-protocol-default-embargo.md)).
The shorter of the two takes effect at once, and the longer becomes a proposed revision; [Default Embargoes](defaults.md#using-defaults) walks through each combination.

Submitting the report is itself a statement of the Reporter's position.

!!! note ""

    A Sender who submits a report without proposing embargo terms SHALL be construed as accepting the Receiver's published default embargo, where one exists.

A Reporter who cannot accept a Recipient's published default can say so by proposing shorter terms with the report.
They can also hold the report back.

!!! note ""

    Participants MAY withhold a report from a Recipient whose published default embargo they are not prepared to accept.

## Addressing Validation Uncertainty

Participants might prefer to delay accepting or rejecting a proposed embargo until after they have had an opportunity to review the report through the validation and (possibly) prioritization processes.
However, other Participants are under no obligation to withhold publication of cases not covered by an active embargo.
A short embargo is therefore recommended until validation concludes, at which point it can be extended with a revision.

!!! note ""

    Participants MAY use short embargo periods to cover their report validation process, and subsequently revise the embargo terms pending the outcome of their report validation and/or prioritization processes.

!!! note ""

    Participants SHOULD remain flexible in adjusting embargo terms as the case evolves.

## Doing It on the Wire

- [How to Establish an Embargo](../../../howto/activitypub/activities/establish_embargo.md) — propose an embargo, and accept or reject a proposal.
- [How to Revise or Terminate an Embargo](../../../howto/activitypub/activities/manage_embargo.md) — propose a change to an active embargo, and accept or reject it.
