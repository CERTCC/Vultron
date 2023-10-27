# Negotiating Embargoes

{% include-markdown "../../../includes/normative.md" %}

Negotiating and entering into a new embargo for a case is only possible
within an embargo "habitable zone" defined in terms of the
[Case State model](../cs/index.md) as laid out below.

The notation for CS model states is explained in
[Case State model](../cs/index.md), but the contextual explanation below should
suffice for now.

!!! note ""

    CVD Participants MUST NOT *propose* or *accept* a new embargo
    negotiation when any of the following conditions are true:

    1.  Information about the vulnerability is already known to the
        public (${q^{cs} \in \cdot\cdot\cdot P \cdot\cdot}$).

    2.  An exploit for the vulnerability is publicly available
        (${q^{cs} \in \cdot\cdot\cdot\cdot X \cdot}$).

    3.  There is evidence that the vulnerability is being actively
        exploited by adversaries (${q^{cs} \in \cdot\cdot\cdot\cdot\cdot A}$).

!!! note ""

    CVD Participants SHOULD NOT *propose* or *accept* a new embargo
    negotiation when the fix for a vulnerability has already been
    deployed ($q^{cs} \in VFDpxa$).

Counterexamples include

- when an embargo is desired to allow for a downstream Vendor to synchronize
their fix delivery or deployment
- when a Vendor has deployed a fix but wants to complete their root cause analysis prior to
releasing information about the vulnerability.

!!! note ""

    CVD Participants MAY *propose* or *accept* a new embargo when the fix
    for a vulnerability is ready but has neither been made public nor
    deployed ($q^{cs} \in VFdpxa$). Such an embargo SHOULD be brief and
    used only to allow Participants to prepare for timely publication or
    deployment.

!!! note ""

    CVD Participants MAY *propose* or *accept* an embargo in all other case
    states (${q^{cs} \in \cdot\cdot\cdot pxa}$).

## Asymmetry in Embargo Negotiation

Asymmetry is inherent in the CVD process because those who currently have the vulnerability information get to decide
with whom they will share it.
This asymmetry puts Reporters at somewhat of an advantage when it comes
to the initial report submission to another Participant.
We discuss some ways to improve (but not fully remove) this asymmetry in [Default Embargoes](#default-embargoes),
but for now we just need to acknowledge that it exists.

!!! note ""  

    Participants MAY *accept* or *reject* any proposed embargo as they
    see fit.

!!! note ""  

    Receivers SHOULD *accept* any embargo proposed by Reporters.

!!! note ""  

    Receivers MAY *propose* embargo terms they find more favorable as
    they see fit.

!!! note ""  

    Participants MAY withdraw (*reject*) their own unaccepted *Proposed*
    embargo.

## Respond Promptly

Timely response to embargo proposals is important. Explicit acceptance
is expected.

!!! note ""

    Participants SHOULD explicitly *accept* or *reject* embargo
    proposals in a timely manner. (For example, embargo agreement or
    rejection SHOULD NOT be tacit.)

!!! note ""
    Participants MAY interpret another Participant's failure to respond
    to an embargo proposal in a timely manner as a *reject*ion of that
    proposal.

!!! note ""
    In the absence of an explicit *accept* or *reject* response from a
    Receiver in a timely manner, the Sender MAY proceed in a manner
    consistent with an EM state of *None* ($q^{em} \in N$).

## No Embargo means No Embargo

Once an embargo negotiation has failed the first time, Participants have
no further obligations.

!!! note ""  

    In a case where the embargo state is _None_ and for which an embargo
    has been *proposed* and either explicitly or tacitly *rejected*,
    Participants MAY take any action they choose with the report in
    question, including immediate publication.

!!! tip "Incentives Matter"

    We deliberately included the clauses "explicitly or tacitly rejected" and "may take any action" above to provide
    incentives for Participants to be declarative and negotiate in good faith.
    Were a rejected embargo proposal to carry _any_ implied obligation to refrain from publication, 
    Participants might be motivated to use delayed or ambiguous responses to impose that obligation on others.
    Our goal is to avoid situations where a Participant is incentivized to simply ignore an embargo proposal
    while proceeding with an expectation that the other Participants are still bound by the proposed-but-inactive embargo terms.
    Therefore we have attempted to be very clear that _only_ active embargoes impose obligations on Participants.

## Don't Give Up Too Soon

The above notwithstanding, Participants are encouraged to try again, especially when no explicit rejection has been
communicated (i.e., in the *tacitly rejected* scenario described above).

!!! note ""  

    Participants SHOULD make reasonable attempts to retry embargo
    negotiations when prior proposals have been *reject*ed or otherwise
    failed to achieve *accept*ance.

## Submitting a Report Before Embargo Negotiations Conclude

Participants need not wait for embargo negotiations to conclude before
submitting a report. However, by doing so, they might give up some of
their leverage over the Receiver in the embargo negotiations.

!!! note ""  

    Participants MAY withhold a report from a Recipient until an initial
    embargo has been accepted.

!!! note ""  

    Submitting a report when an embargo proposal is pending
    ($q^{em} \in P$) SHALL be construed as the Sender's acceptance
    ($q^{em} \in P \xrightarrow{a} A$) of the terms proposed regardless
    of whether the Sender or Receiver was the proposer.

## Addressing Validation Uncertainty

Participants might prefer to delay accepting or rejecting a proposed
embargo until after they have had an opportunity to review the report
through the validation and (possibly) prioritization processes. However,
because other Participants are under no obligation to withhold
publication of cases not covered by an active embargo, we recommend that
a short embargo be used until the validation process concludes, at which
point, it can be extended with a revision.

!!! note ""

    Participants MAY use short embargo periods to cover their report
    validation process, and subsequently revise the embargo terms
    pending the outcome of their report validation and/or prioritization
    processes.

!!! note ""  

    Participants SHOULD remain flexible in adjusting embargo terms as
    the case evolves.
