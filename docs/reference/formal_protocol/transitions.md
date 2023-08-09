# Transition Functions {#sec:protocol_transition_functions}

Revisiting the formal protocol definition from the [introduction](/reference/formal_protocol/), 

> $succ$ is a partial function mapping for each $i$ and $j$,
> $$S_i \times M_{ij} \rightarrow S_i \textrm{ and } S_i \times M_{ji} \rightarrow S_i$$
> $succ(s,x)$ is the state entered after a process transmits or receives
> message $x$ in state $s$. It is a transmission if $x$ is from $M_{ij}$
> and a reception if $x$ is from $M_{ji}$.

In this section, we describe the transition functions for the RM, EM, and CVD Case processes, respectively.
Note that while the RM process is largely independent of the other two process models, the EM and CVD process models 
have some noteworthy interactions, which we will cover in detail.

## RM Transition Functions

Because it only reflects an individual Participant's report handling status,
the RM process operates largely independent of both the EM and CS processes.
Otherwise,

!!! note ""

    Participants MUST be in RM $Accepted$ to send a report ($RS$) to
    someone else.

!!! note ""

    Participants SHOULD send $RI$ when the report validation process
    ends in an $invalid$ determination.

!!! note ""

    Participants SHOULD send $RV$ when the report validation process
    ends in a $valid$ determination.

!!! note ""

    Participants SHOULD send $RD$ when the report prioritization process
    ends in a $deferred$ decision.

!!! note ""

    Participants SHOULD send $RA$ when the report prioritization process
    ends in an $accept$ decision.

!!! note ""

    Participants SHOULD send $RC$ when the report is closed.

!!! note ""

    Participants SHOULD send $RE$ regardless of the state when any error
    is encountered.
   
!!! note ""

    Recipients MAY ignore messages received on $Closed$ cases.

!!! note ""
  
    Recipients SHOULD send $RK$ in acknowledgment of any $R*$ message
    except $RK$ itself.

!!! note ""

    Vendor Recipients should send both $CV$ and $RK$ in response to a
    report submission ($RS$). If the report is new to the Vendor, it
    MUST transition $q^{cs} \xrightarrow{\mathbf{V}}Vfd\cdot\cdot\cdot$.

!!! note ""

    Any $R*$ message, aside from $RS$, received by recipient in
    $q^{rm} \in S$ is an error because it indicates the sender thought
    the receiver was aware of a report they had no knowledge of. The
    Recipient SHOULD respond with both an $RE$ to signal the error and
    $GI$ to find out what the sender expected.

!!! note ""

    Recipients SHOULD acknowledge $RE$ messages ($RK$) and inquire
    ($GI$) as to the nature of the error.

{== Table [\[tab:rm_send\]](#tab:rm_send){reference-type="ref"
reference="tab:rm_send"} ==} lists each RM message type and the states in which that
message is appropriate to send along with the corresponding sender state
transition. {== Table
[\[tab:rm_receive\]](#tab:rm_receive){reference-type="ref"
reference="tab:rm_receive"} ==} lists the effects of receiving
RM messages on the receiving Participant's state coupled with the expected response
message.

## EM Transition Functions

The appropriate Participant behavior in the EM process depends on whether the case state
$q^{cs}$ is in $\cdot\cdot\cdot pxa$ or not.

!!! note ""

    Participants SHALL NOT negotiate embargoes where the vulnerability
    or its exploit is public or attacks are known to have occurred.

!!! note ""

    Participants MAY begin embargo negotiations before sending the
    report itself in an $RS$ message. Therefore, it is *not* an error
    for an $E*$ message to arrive while the Recipient is unaware of the
    report ($q^{rm} \in S$).

!!! note ""

    Participants MAY reject any embargo proposals or revisions for any
    reason.

!!! note ""

    If information about the vulnerability or an exploit for it has been
    made public, Participants SHALL terminate the embargo
    ($q^{cs} \in \{\cdot\cdot\cdot P \cdot\cdot, \cdot\cdot\cdot\cdot X \cdot\}$).

!!! note ""

    If attacks are known to have occurred, Participants SHOULD terminate
    the embargo ($q^{cs} \in \cdot\cdot\cdot\cdot\cdot A$).

!!! note ""

    Participants SHOULD send $EK$ in acknowledgment of any other $E*$
    message except $EK$ itself.

!!! note ""

    Participants SHOULD acknowledge ($EK$) and inquire ($GI$) about the
    nature of any error reported by an incoming $EE$ message.

{== Table [\[tab:em_send\]](#tab:em_send){reference-type="ref"
reference="tab:em_send"} ==} lists each EM message type and the states in which that
message is appropriate to send along with the corresponding sender state
transition. {== Table
[\[tab:em_receive\]](#tab:em_receive){reference-type="ref"
reference="tab:em_receive"} ==} lists the effects of receiving an
EM message to the receiving Participant's state, grouped by the EM message type received.

## CVD Transition Functions

!!! tip inline end "Participant-Specific State Messages Promote Shared Situation Awareness"

    Effective coordination is usually improved with Participants' mutual awareness of each other's state, of course.

The Vendor-specific portions of the CS (*Vendor Awareness*, *Fix Ready*, and
*Fix Deployed*) are per-Participant states.
Therefore, the receiver of a message indicating another Participant has changed their $\{v,V\}$, $\{f,F\}$ or $\{d,D\}$
status is not expected to change their own state as a result.

However, this is not the case for the remainder of the CS substates.
As above, the appropriate Participant response to receiving CS messages (namely, those surrounding *Public Awareness*, 
*Exploit Public*, or *Attacks Observed*) depends on the state of the EM process.

!!! note ""

    Participants SHALL initiate embargo termination upon becoming aware
    of publicly available information about the vulnerability or its
    exploit code.


!!! note ""

    Participants SHOULD initiate embargo termination upon becoming aware
    of attacks against an otherwise unpublished vulnerability.

{== Table [\[tab:cvd_send\]](#tab:cvd_send){reference-type="ref"
reference="tab:cvd_send"} ==} lists each CVD message type and the states in which that
message is appropriate to send along with the corresponding sender state
transition. {== Table
[\[tab:cvd_receive\]](#tab:cvd_receive){reference-type="ref"
reference="tab:cvd_receive"} ==} lists the effects of receiving a
CS message to the receiving Participant's state coupled with the expected response message.

## General Transition Functions

Finally, for the sake of completeness, in {== Tables [\[tab:gen_send\]](#tab:gen_send){reference-type="ref"
reference="tab:gen_send"} and
[\[tab:gen_receive\]](#tab:gen_receive){reference-type="ref"
reference="tab:gen_receive"} ==}, we show that general inquiries, acknowledgments, and errors are otherwise independent 
of the rest of the processes.
No state changes are expected to occur based on the receipt of a General message.

!!! tip "General Messages are not a *No-Op*"

    Note that we do not mean to imply that the *content* of such a message is expected to have no effect on the progression 
    of a case, merely that the act of sending or receiving a general message itself does not imply any necessary state 
    change to either the sender or receiver Participants.

{== Table [\[tab:gen_send\]](#tab:gen_send){reference-type="ref"
reference="tab:gen_send"} ==} lists each general message and the states in
which it is appropriate to send along with the corresponding sender
state. 
{== Table
[\[tab:gen_receive\]](#tab:gen_receive){reference-type="ref"
reference="tab:gen_receive"} ==} lists the effects of receiving a general
message to the receiving Participant's state coupled with the expected
response message.
