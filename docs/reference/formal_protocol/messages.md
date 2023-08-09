# Message Types {#sec:protocol_message_types}

In {== §[1.3](#sec:protocol_states){reference-type="ref"
reference="sec:protocol_states"} ==}, we identified four main roles in the
MPCVD process:
Finder/Reporter, Vendor, Coordinator, and Deployer. Here we will examine
the messages passed between them. Revisiting the definitions from
{== §[1.1](#sec:protocol_definition){reference-type="ref"
reference="sec:protocol_definition"} ==},

> $\langle M_{ij} \rangle_{i,j=1}^N$ are $N^2$ disjoint finite sets with
> $M_{ii}$ empty for all $i$: $M_{ij}$ represents the messages that can
> be sent from process $i$ to process $j$.

The message types in our proposed MPCVD protocol arise primarily from the
following principle taken directly from the CVD Guide [@householder2017cert]:

> **Avoid Surprise** -- As with most situations in which multiple
> parties are engaged in a potentially stressful and contentious
> negotiation, surprise tends to increase the risk of a negative
> outcome. The importance of clearly communicating expectations across
> all parties involved in a CVD process cannot be overemphasized. If we
> expect cooperation between all parties and stakeholders, we should do
> our best to match their expectations of being "in the loop" and
> minimize their surprise. Publicly disclosing a vulnerability without
> coordinating first can result in panic and an aversion to future
> cooperation from Vendors and Finders alike. CVD promotes continued
> cooperation and increases the likelihood that future vulnerabilities
> will also be addressed and remedied.

Now we condense that principle into the following protocol
recommendation:

-   Participants whose state changes in the RM, EM, or CVD State Models SHOULD send a message to
    other Participants for each transition.

If you are looking for a one-sentence summary of the entire
MPCVD protocol,
that was it.

As a reminder, those transitions are

-   RM state transitions $\Sigma^{rm} = \{ r,v,a,i,d,c\}$

-   EM state transitions $\Sigma^{em} = \{ p,a,r,t\}$

-   CVD state transitions
    $\Sigma^{cs} = \{\mathbf{V},\mathbf{F},\mathbf{D},\mathbf{P},\mathbf{X},\mathbf{A}\}$

We will address the specific circumstances when each message should be
emitted in
{== §[1.7](#sec:protocol_transition_functions){reference-type="ref"
reference="sec:protocol_transition_functions"} ==}, but first we need to
introduce the message types this recommendation implies. We cover
messages associated with each state model, in turn, below, concluding
the section with a few message types not directly connected to any
particular state model.

## RM Message Types {#sec:rm_message_types}

With the exception of the Finder/Reporter, each Participant's
involvement in a CVD case starts with the receipt of a report
from another Participant who is already in the $Accepted$
($q^{rm} \in A$) state.[^1]

Report Submission

:   ($RS$) is a message from one Participant to a new Participant
    containing a vulnerability report.

We continue with a list of state-change messages *originating* from a
Participant in the RM process:

Report Invalid

:   ($RI$) is a message indicating the Participant has designated the
    report as invalid.

Report Valid

:   ($RV$) is a message indicating the Participant has designated the
    report as valid.

Report Deferred

:   ($RD$) is a message indicating the Participant is deferring further
    action on a report.

Report Accepted

:   ($RA$) is a message indicating the Participant has accepted the
    report for further action.

Report Closed

:   ($RC$) is a message indicating the Participant has closed the
    report.

Report Acknowledgement

:   ($RK$) is a message acknowledging the receipt of a report.

Report Error

:   ($RE$) is a message indicating a Participant received an unexpected
    RM message.

A summary of the RM
message types is shown in [\[eq:m_rm\]](#eq:m_rm){reference-type="eqref"
reference="eq:m_rm"}.

$$\label{eq:m_rm}
M^{rm} = \{RS,RI,RV,RD,RA,RC,RK,RE\}$$

All state changes are from the Participant's (sender's) perspective, not
the recipient's perspective. We will see in
{== §[1.7](#sec:protocol_transition_functions){reference-type="ref"
reference="sec:protocol_transition_functions"} ==} that the receipt of a
*Report Submission* is the only message whose *receipt* directly
triggers an RM state
change in the receiver. All other RM messages are used to convey the sender's
status.

-   Participants SHOULD act in accordance with their own policy and
    process in deciding when to transition states in the
    RM model.

-   Participants SHOULD NOT mark duplicate reports as invalid.

-   Instead, duplicate reports SHOULD pass through $Valid$
    ($q^{rm} \in V$), although they MAY be subsequently (immediately or
    otherwise) deferred ($q^{rm} \in V \xrightarrow{d} D$) in favor of
    the original.

-   Participants SHOULD track the RM states of the other Participants in
    the case.

An example object model for such tracking is described in
{== §[\[sec:case_object\]](#sec:case_object){reference-type="ref"
reference="sec:case_object"} ==}. Furthermore, while these messages are
expected to inform the receiving Participant's choices in their own
RM process, this
protocol intentionally does not specify any other recipient
RM state changes
upon receipt of an RM message.

## EM Message Types {#sec:em_message_types}

Whereas the RM
process is unique to each Participant, the EM process is global to the case. Therefore,
we begin with the list of message types a Participant SHOULD emit when
their EM state
changes.

Embargo Proposal

:   ($EP$) is a message containing proposed embargo terms (e.g.,
    date/time of expiration).

Embargo Proposal Rejection

:   ($ER$) is a message indicating the Participant has rejected an
    embargo proposal.

Embargo Proposal Acceptance

:   ($EA$) is a message indicating the Participant has accepted an
    embargo proposal.

Embargo Revision Proposal

:   ($EV$) is a message containing a proposed revision to embargo terms
    (e.g., date/time of expiration).

Embargo Revision Rejection

:   ($EJ$) is a message indicating the Participant has rejected a
    proposed embargo revision.

Embargo Revision Acceptance

:   ($EC$) is a message indicating the Participant has accepted a
    proposed embargo revision.

Embargo Termination

:   ($ET$) is a message indicating the Participant has terminated an
    embargo (including the reason for termination). Note that an
    *Embargo Termination* message is intended to have immediate effect.

    -   If an early termination is desired but the termination date/time
        is in the future, this SHOULD be achieved through an *Embargo
        Revision Proposal* and additional communication as necessary to
        convey the constraints on the proposal.

Embargo Acknowledgement

:   ($EK$) is a message acknowledging receipt of an
    EM message.

Embargo Error

:   ($EE$) is a message indicating a Participant received an unexpected
    EM message.

A summary of the EM
message types is shown in [\[eq:m_em\]](#eq:m_em){reference-type="eqref"
reference="eq:m_em"}.

$$\label{eq:m_em}
M^{em} = \{ EP,ER,EA,EV,EJ,EC,ET,EK,EE \}$$

## CS Message Types {#sec:cs_message_types}

From the CS process
in {== §[\[sec:model\]](#sec:model){reference-type="ref"
reference="sec:model"} ==}, the following is the list of messages associated
with CS state
changes:

Vendor Awareness

:   ($CV$) is a message to other Participants indicating that a report
    has been delivered to a specific Vendor. Note that this is an
    announcement of a state change for a Vendor, not the actual report
    to the Vendor, which is covered in the **Report Submission** ($RS$)
    above.

    -   **Vendor Awareness** messages SHOULD be sent only by
        Participants with direct knowledge of the notification (i.e.,
        either by the Participant who sent the report to the Vendor or
        by the Vendor upon receipt of the report).

Fix Readiness

:   ($CF$) is a message from a Participant (usually a Vendor) indicating
    that a specific Vendor has a fix ready.

Fix Deployed

:   ($CD$) is a message from a Participant (usually a Deployer)
    indicating that they have completed their fix deployment process.
    This message is expected to be rare in most
    MPCVD cases
    because Deployers are rarely included in the coordination effort.

Public Awareness

:   ($CP$) is a message from a Participant indicating that they have
    evidence that the vulnerability is known to the public. This message
    might be sent after a Participant has published their own advisory
    or if they have observed public discussion of the vulnerability.

Exploit Public

:   ($CX$) is a message from a Participant indicating that they have
    evidence that an exploit for the vulnerability is publicly
    available. This message might be sent after a Participant has
    published their own exploit code, or if they have observed exploit
    code available to the public.

Attacks Observed

:   ($CA$) is a message from a Participant indicating that they have
    evidence that attackers are exploiting the vulnerability in attacks.

CS Acknowledgement

:   ($CK$) is a message acknowledging receipt of a
    CS message.

CS Error

:   ($CE$) is a message indicating a Participant received an unexpected
    CS message.

A summary of the CS
message types is shown in [\[eq:m_cs\]](#eq:m_cs){reference-type="eqref"
reference="eq:m_cs"}.

$$\label{eq:m_cs}
M^{cs} = \{CV,CF,CD,CP,CX,CA,CK,CE \}$$

## Other Message Types {#sec:gen_message_types}

Finally, there are a few additional message types required to tie the
coordination process together. Most of these message types are *not*
associated with a specific state change, although they might trigger
activities or events that could cause a state change in a Participant
(and therefore trigger one or more of the above message types to be
sent).

General Inquiry

:   ($GI$) is a message from a Participant to one or more other
    Participants to communicate non-state-change information. Examples
    of general inquiry messages include but are not limited to

    -   asking or responding to a question

    -   requesting an update on a Participant's status

    -   requesting review of a draft publication

    -   suggesting a potential Participant to be added to a case

    -   coordinating other events

    -   resolving a loss of Participant state synchronization

General Acknowledgement

:   ($GK$) is a message from a Participant indicating their receipt of
    any of the other messages listed here.

General Error

:   ($GE$) is a message indicating a general error has occurred.

A summary of the General message types is shown in
[\[eq:m_gm\]](#eq:m_gm){reference-type="eqref" reference="eq:m_gm"}.

$$\label{eq:m_gm}
M^{*} = \{ GI,GK,GE \}$$

## Message Type Redux

Thus, the complete set of possible messages between processes is
$M_{i,j} = M^{rm} \cup M^{em} \cup M^{cs} \cup M^{*}$. For convenience,
we collected these into
[\[eq:message_types\]](#eq:message_types){reference-type="eqref"
reference="eq:message_types"} and provide a summary in Table
[\[tab:message_types\]](#tab:message_types){reference-type="ref"
reference="tab:message_types"}.

$$\label{eq:message_types}
    M_{i,j} =
        \left\{ 
        \begin{array}{l}
                RS,RI,RV,RD,RA,RC,RK,\\
                RE,EP,ER,EA,EV,EJ,EC,\\
                ET,EK,EE,CV,CF,CD,CP,\\
                CX,CA,CK,CE,GI,GK,GE\\
        \end{array}
        \right\}\text{\quad}
        \parbox{10em}{ where $i \neq j$; \\
        $\varnothing$ otherwise;
        \\for $i,j \leq N$}$$

Message formats are left as future work in
{== §[\[sec:msg_formats\]](#sec:msg_formats){reference-type="ref"
reference="sec:msg_formats"} ==}.

