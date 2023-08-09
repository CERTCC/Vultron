# A Formal Protocol Definition for MPCVD {#sec:formal_protocol}

The MPCVD process can be described as a Communicating Hierarchical State Machine.
In this section, we begin by laying out the requirements for a formal protocol
definition followed by a step-by-step walkthrough of each of those requirements
as they relate to the [RM](/topics/process_models/rm/), [EM](/topics/process_models/em/), and [CS](/topics/process_models/cs/)
models described elsewhere.

## Communication Protocol Definitions {#sec:protocol_definition}

A communication protocol allows independent processes, represented as finite state machines, to coordinate their state 
transitions through the passing of messages. {== Brand and Zafiropulo [@brand1983communicating] ==}
defined a protocol as follows. 

!!! note "_Protocol_ Formally Defined"

    A **protocol** with $N$ processes is a quadruple:

    $$\label{eq:protocol}
    protocol = 
        \Big \langle 
            { \langle S_i \rangle }^N_{i=1}, 
            { \langle o_i \rangle }^N_{i=1},
            { \langle M_{i,j} \rangle}^N_{i,j=1},
            { succ }
        \Big \rangle$$

    Where

    -   $N$ is a positive integer representing the number of processes.

    -   $\langle S_i \rangle_{i=1}^N$ are $N$ disjoint finite sets ($S_i$
    represents the set of states of process $i$).

    -   Each $o_i$ is an element of $S_i$ representing the initial state of
    process $i$.

    -   $\langle M_{ij} \rangle_{i,j=1}^N$ are $N^2$ disjoint finite sets
    with $M_{ii}$ empty for all $i$. $M_{ij}$ represents the messages
    that can be sent from process $i$ to process $j$,

    -   $succ$ is a partial function mapping for each $i$ and $j$,
    $$S_i \times M_{ij} \rightarrow S_i \textrm{ and } S_i \times M_{ji} \rightarrow S_i$$
    $succ(s,x)$ is the state entered after a process transmits or
    receives message $x$ in state $s$. It is a transmission if $x$ is
    from $M_{ij}$ and a reception if $x$ is from $M_{ji}$.

!!! note "_Global State_ Formally Defined"

    The **global state** of a protocol given by the above is a pair $\langle S, C \rangle$, where

    -   $S$ is an $N$-tuple of states $\langle s_1,\dots,s_N \rangle$ with
    each $s_i$ representing the current state of process $i$.

    -   $C$ is an $N^2$-tuple
    $\langle c_{1,1},\dots, c_{1,N}, c_{2,1}, \dots \dots, c_{N,N} \rangle$,
    where each $c_{i,j}$ is a sequence of messages from $M_{i,j}$. The
    message sequence $c_{i,j}$ represents the contents of the channel
    from process $i$ to $j$. (Note that $c_{i,j}$ is empty when $i = j$
    since processes are presumed to not communicate with themselves.)

We detail each of these in the subsequent sections of this page:

- $N$ in {== §[1.2](#sec:protocol_n_processes){reference-type="ref"
reference="sec:protocol_n_processes"} ==}, 
- ${ \langle S_i \rangle}^N_{i=1}$
in {== §[1.3](#sec:protocol_states){reference-type="ref"
reference="sec:protocol_states"} ==}, 
- ${ \langle o_i \rangle }^N_{i=1}$ in
{== §[1.5](#sec:protocol_starting_states){reference-type="ref"
reference="sec:protocol_starting_states"} ==},
- ${ \langle M_{i,j} \rangle }^N_{i,j=1}$ in
{== §[1.6](#sec:protocol_message_types){reference-type="ref"
reference="sec:protocol_message_types"} ==}, and
- ${ \langle {succ} \rangle }_{i=1}^N$ in
{== §[1.7](#sec:protocol_transition_functions){reference-type="ref"
reference="sec:protocol_transition_functions"} ==}.

## Number of Processes {#sec:protocol_n_processes}

The processes we are concerned with represent the different Participants
in their roles (Finder, Vendor, Coordinator, Deployer, and Other). Each
Participant has their own process, but Participants might take on
multiple roles in a given case.

!!! note "_Number of Processes_"

    The total number of processes $N$ is simply the count of unique Participants.

    $$N = |Participants| = | Reporters \cup Vendors \cup Coordinators \cup Deployers \cup Others |$$


## Message Types {#sec:protocol_message_types}

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

### RM Message Types {#sec:rm_message_types}

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

### EM Message Types {#sec:em_message_types}

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

### CS Message Types {#sec:cs_message_types}

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

### Other Message Types {#sec:gen_message_types}

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

### Message Type Redux

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

## Transition Functions {#sec:protocol_transition_functions}

Revisiting the formal protocol definition from the beginning of the
chapter,

> $succ$ is a partial function mapping for each $i$ and $j$,
> $$S_i \times M_{ij} \rightarrow S_i \textrm{ and } S_i \times M_{ji} \rightarrow S_i$$
> $succ(s,x)$ is the state entered after a process transmits or receives
> message $x$ in state $s$. It is a transmission if $x$ is from $M_{ij}$
> and a reception if $x$ is from $M_{ji}$.

In this section, we describe the transition functions for the
RM,
EM, and
CVD Case processes,
respectively. Note that while the RM process is largely independent of the
other two process models, the EM and CVD process models have some noteworthy
interactions, which we will cover in detail.

### RM Transition Functions

Because it only reflects an individual Participant's report handling
status, the RM
process operates largely independent of both the EM and CS processes. Otherwise,

-   Participants MUST be in RM $Accepted$ to send a report ($RS$) to
    someone else.

-   Participants SHOULD send $RI$ when the report validation process
    ends in an $invalid$ determination.

-   Participants SHOULD send $RV$ when the report validation process
    ends in a $valid$ determination.

-   Participants SHOULD send $RD$ when the report prioritization process
    ends in a $deferred$ decision.

-   Participants SHOULD send $RA$ when the report prioritization process
    ends in an $accept$ decision.

-   Participants SHOULD send $RC$ when the report is closed.

-   Participants SHOULD send $RE$ regardless of the state when any error
    is encountered.

-   Recipients MAY ignore messages received on $Closed$ cases.

-   Recipients SHOULD send $RK$ in acknowledgment of any $R*$ message
    except $RK$ itself.

-   Vendor Recipients should send both $CV$ and $RK$ in response to a
    report submission ($RS$). If the report is new to the Vendor, it
    MUST transition $q^{cs} \xrightarrow{\mathbf{V}}Vfd\cdot\cdot\cdot$.

-   Any $R*$ message, aside from $RS$, received by recipient in
    $q^{rm} \in S$ is an error because it indicates the sender thought
    the receiver was aware of a report they had no knowledge of. The
    Recipient SHOULD respond with both an $RE$ to signal the error and
    $GI$ to find out what the sender expected.

-   Recipients SHOULD acknowledge $RE$ messages ($RK$) and inquire
    ($GI$) as to the nature of the error.

Table [\[tab:rm_send\]](#tab:rm_send){reference-type="ref"
reference="tab:rm_send"} lists each RM message type and the states in which that
message is appropriate to send along with the corresponding sender state
transition. Table
[\[tab:rm_receive\]](#tab:rm_receive){reference-type="ref"
reference="tab:rm_receive"} lists the effects of receiving
RM messages on the
receiving Participant's state coupled with the expected response
message.

### EM Transition Functions

The appropriate Participant behavior in the EM process depends on whether the case state
$q^{cs}$ is in $\cdot\cdot\cdot pxa$ or not.

-   Participants SHALL NOT negotiate embargoes where the vulnerability
    or its exploit is public or attacks are known to have occurred.

-   Participants MAY begin embargo negotiations before sending the
    report itself in an $RS$ message. Therefore, it is *not* an error
    for an $E*$ message to arrive while the Recipient is unaware of the
    report ($q^{rm} \in S$).

-   Participants MAY reject any embargo proposals or revisions for any
    reason.

-   If information about the vulnerability or an exploit for it has been
    made public, Participants SHALL terminate the embargo
    ($q^{cs} \in \{\cdot\cdot\cdot P \cdot\cdot, \cdot\cdot\cdot\cdot X \cdot\}$).

-   If attacks are known to have occurred, Participants SHOULD terminate
    the embargo ($q^{cs} \in \cdot\cdot\cdot\cdot\cdot A$).

-   Participants SHOULD send $EK$ in acknowledgment of any other $E*$
    message except $EK$ itself.

-   Participants SHOULD acknowledge ($EK$) and inquire ($GI$) about the
    nature of any error reported by an incoming $EE$ message.

Table [\[tab:em_send\]](#tab:em_send){reference-type="ref"
reference="tab:em_send"} lists each EM message type and the states in which that
message is appropriate to send along with the corresponding sender state
transition. Table
[\[tab:em_receive\]](#tab:em_receive){reference-type="ref"
reference="tab:em_receive"} lists the effects of receiving an
EM message to the
receiving Participant's state, grouped by the EM message type received.

### CVD Transition Functions

The Vendor-specific portions of the CS (*Vendor Awareness*, *Fix Ready*, and
*Fix Deployed*) are per-Participant states. Therefore, the receiver of a
message indicating another Participant has changed their $\{v,V\}$,
$\{f,F\}$ or $\{d,D\}$ status is not expected to change their own state
as a result.[^2]

However, this is not the case for the remainder of the
CS substates. As
above, the appropriate Participant response to receiving
CS messages (namely,
those surrounding *Public Awareness*, *Exploit Public*, or *Attacks
Observed*) depends on the state of the EM process.

-   Participants SHALL initiate embargo termination upon becoming aware
    of publicly available information about the vulnerability or its
    exploit code.

-   Participants SHOULD initiate embargo termination upon becoming aware
    of attacks against an otherwise unpublished vulnerability.

Table [\[tab:cvd_send\]](#tab:cvd_send){reference-type="ref"
reference="tab:cvd_send"} lists each CVD message type and the states in which that
message is appropriate to send along with the corresponding sender state
transition. Table
[\[tab:cvd_receive\]](#tab:cvd_receive){reference-type="ref"
reference="tab:cvd_receive"} lists the effects of receiving a
CS message to the
receiving Participant's state coupled with the expected response
message.

### General Transition Functions

Finally, for the sake of completeness, in Tables
[\[tab:gen_send\]](#tab:gen_send){reference-type="ref"
reference="tab:gen_send"} and
[\[tab:gen_receive\]](#tab:gen_receive){reference-type="ref"
reference="tab:gen_receive"}, we show that general inquiries,
acknowledgments, and errors are otherwise independent of the rest of the
processes. No state changes are expected to occur based on the receipt
of a General message. Note that we do not mean to imply that the
*content* of such a message is expected to have no effect on the
progression of a case, merely that the act of sending or receiving a
general message itself does not imply any necessary state change to
either the sender or receiver Participants.

Table [\[tab:gen_send\]](#tab:gen_send){reference-type="ref"
reference="tab:gen_send"} lists each general message and the states in
which it is appropriate to send along with the corresponding sender
state. Table
[\[tab:gen_receive\]](#tab:gen_receive){reference-type="ref"
reference="tab:gen_receive"} lists the effects of receiving a general
message to the receiving Participant's state coupled with the expected
response message.

## Formal MPCVD Protocol Redux {#sec:formal_protocol_redux}

In this chapter, we have formally defined an
MPCVD protocol

$${protocol}_{MPCVD} = 
    \Big \langle 
        { \langle S_i \rangle }^N_{i=1}, 
        { \langle o_i \rangle }^N_{i=1},
        { \langle M_{i,j} \rangle}^N_{i,j=1},
        { succ }
    \Big \rangle$$

where

-   $N$ is a positive integer representing the number of
    MPCVD
    Participants in a case and

-   $\langle S_i \rangle_{i=1}^N$ are $N$ disjoint finite sets in which
    each $S_i$ represents the set of states of a given Participant $i$
    [\[eq:protocol_states_reduced\]](#eq:protocol_states_reduced){reference-type="eqref"
    reference="eq:protocol_states_reduced"}, as refined by
    [\[eq:protocol_states_vendor\]](#eq:protocol_states_vendor){reference-type="eqref"
    reference="eq:protocol_states_vendor"},
    [\[eq:protocol_states_nonvendor_deployer\]](#eq:protocol_states_nonvendor_deployer){reference-type="eqref"
    reference="eq:protocol_states_nonvendor_deployer"},
    [\[eq:protocol_states_reporter\]](#eq:protocol_states_reporter){reference-type="eqref"
    reference="eq:protocol_states_reporter"}, and
    [\[eq:protocol_states_other\]](#eq:protocol_states_other){reference-type="eqref"
    reference="eq:protocol_states_other"}.

-   ${ \langle o_i \rangle }^N_{i=1}$ is the set of starting states
    across all Participants in which each $o_i$ is an element of $S_i$
    representing the initial state of each Participant $i$, as detailed
    in
    [\[eq:protocol_start_state_vendor\]](#eq:protocol_start_state_vendor){reference-type="eqref"
    reference="eq:protocol_start_state_vendor"}
    [\[eq:protocol_start_state_deployer\]](#eq:protocol_start_state_deployer){reference-type="eqref"
    reference="eq:protocol_start_state_deployer"},
    [\[eq:protocol_start_state_other\]](#eq:protocol_start_state_other){reference-type="eqref"
    reference="eq:protocol_start_state_other"}, and
    [\[eq:protocol_start_state_finder\]](#eq:protocol_start_state_finder){reference-type="eqref"
    reference="eq:protocol_start_state_finder"}.

-   $\langle M_{ij} \rangle_{i,j=1}^N$ are $N^2$ disjoint finite sets
    with $M_{ii}$ empty for all $i$. $M_{ij}$ represents the messages
    that can be sent from process $i$ to process $j$. A list of message
    types is defined in
    [\[eq:message_types\]](#eq:message_types){reference-type="eqref"
    reference="eq:message_types"} and summarized in Table
    [\[tab:message_types\]](#tab:message_types){reference-type="ref"
    reference="tab:message_types"}.

-   $succ$ is a partial function mapping for each $i$ and $j$,
    $$S_i \times M_{ij} \rightarrow S_i \textrm{ and } S_i \times M_{ji} \rightarrow S_i$$
    indicating the state changes arising from the sending and receiving
    of messages between Participants. The full set of transition
    function definitions for our protocol is shown in Tables
    [\[tab:rm_send\]](#tab:rm_send){reference-type="ref"
    reference="tab:rm_send"},
    [\[tab:rm_receive\]](#tab:rm_receive){reference-type="ref"
    reference="tab:rm_receive"},
    [\[tab:em_send\]](#tab:em_send){reference-type="ref"
    reference="tab:em_send"},
    [\[tab:em_receive\]](#tab:em_receive){reference-type="ref"
    reference="tab:em_receive"},
    [\[tab:cvd_send\]](#tab:cvd_send){reference-type="ref"
    reference="tab:cvd_send"},
    [\[tab:cvd_receive\]](#tab:cvd_receive){reference-type="ref"
    reference="tab:cvd_receive"},
    [\[tab:gen_send\]](#tab:gen_send){reference-type="ref"
    reference="tab:gen_send"}, and
    [\[tab:gen_receive\]](#tab:gen_receive){reference-type="ref"
    reference="tab:gen_receive"}.

A summary diagram of the MPCVD state model $S_i$ for an individual
Participant is shown in Figure
[\[fig:bingo_card\]](#fig:bingo_card){reference-type="ref"
reference="fig:bingo_card"}.


[^1]: As we discuss in
    {== §[\[sec:finder_hidden\]](#sec:finder_hidden){reference-type="ref"
    reference="sec:finder_hidden"} ==}, the Finder's states
    $q^{rm} \in \{R,I,V\}$ are not observable to the
    CVD process
    because Finders start coordination only when they have already
    reached $q^{rm} = A$.

[^2]: Effective coordination is usually improved with Participants'
    mutual awareness of each other's state, of course.

[^3]: "Yes-And" is a heuristic taken from improvisational theatre in
    which Participants are encouraged to agree with whatever their
    counterpart suggests and add to it rather than reject it outright.
    It serves as a good model for cooperation among parties who share an
    interest in a positive outcome.
