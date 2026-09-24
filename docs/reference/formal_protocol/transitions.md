---
stakeholder_type: [platform-developer]
level: 400
---

# Transition Functions

{% include-markdown "../../includes/normative.md" %}

This page gives the transition function $succ$ of the formal protocol for the Report Management (RM), Embargo Management (EM), and Case State (CS) processes, plus the general messages.
It is for implementers who need the exact sender and receiver behavior for each message type.
The RM process is largely independent of the other two, while the EM and CS processes interact, as the EM and CS sections below show.

The [protocol definition](protocol_definition.md) introduces $succ$ as the fourth element of the protocol quadruple:

!!! note "Transition Function Defined"

    $succ$ is a partial function mapping for each $i$ and $j$,
    
    $$S_i \times M_{ij} \rightarrow S_i \textrm{ and } S_i \times M_{ji} \rightarrow S_i$$

    $succ(s,x)$ is the state entered after a process transmits or receives
    message $x$ in state $s$. It is a transmission if $x$ is from $M_{ij}$
    and a reception if $x$ is from $M_{ji}$.

!!! tip "Notation Conventions on this Page"

    - By convention, CS states are labeled in the order $vfdpxa$.
    - Participant state is a tuple of the individual RM, EM, and CS states $S_i = (q^{rm}, q^{em}, q^{cs})$, in the order [States](states.md) defines.
    - Dots ($\cdot$) in states indicate single wildcards. For example, $Vfd \cdot \cdot \cdot$ includes $Vfdpxa, VfdPxA, VfdPXA, etc.$
    - Asterisks ($*$) indicate arbitrary wildcards.
    - Negation ($\lnot$) indicates any state other than the one or ones named. For example, $\lnot \{S,C\}$ in the RM position means any RM state except $Start$ and $Closed$.
    - Dashes ($−$) indicate no state change.
    - Left-harpoons ($\leftharpoondown$) indicate a message received.
    - Right-harpoons ($\rightharpoonup$) indicate a message sent.

## RM Transition Functions

Because it only reflects an individual Participant's report handling status,
the RM process operates largely independent of both the EM and CS processes.
Otherwise,

!!! note "[RMB-13](../../reference/specs/protocol.md#rmb-13)"

    Participants MUST be in RM $Accepted$ to send a report ($RS$) to
    someone else.

!!! note "[RMB-11](../../reference/specs/protocol.md#rmb-11)"

    Participants SHOULD send $RI$ when the report validation process
    ends in an $invalid$ determination.

!!! note "[RMB-10](../../reference/specs/protocol.md#rmb-10)"

    Participants SHOULD send $RV$ when the report validation process
    ends in a $valid$ determination.

!!! note "[RMB-12](../../reference/specs/protocol.md#rmb-12)"

    Participants SHOULD send $RD$ when the report prioritization process
    ends in a $deferred$ decision.

!!! note "[RMB-13](../../reference/specs/protocol.md#rmb-13)"

    Participants SHOULD send $RA$ when the report prioritization process
    ends in an $accept$ decision.

!!! note "[RMB-14](../../reference/specs/protocol.md#rmb-14)"

    Participants SHOULD send $RC$ when the report is closed.

!!! note "[RMB-07](../../reference/specs/protocol.md#rmb-07)"

    Participants SHOULD send $RE$ regardless of the state when any error
    is encountered.

!!! note "[RMB-14](../../reference/specs/protocol.md#rmb-14)"

    Recipients MAY ignore messages received on $Closed$ cases.

!!! note "[RMB-08](../../reference/specs/protocol.md#rmb-08)"

    Recipients SHOULD send $RK$ in acknowledgment of any $R*$ message
    except $RK$ itself.

!!! note "[RMB-01](../../reference/specs/protocol.md#rmb-01)"

    Vendor Recipients should send both $CV$ and $RK$ in response to a
    report submission ($RS$). If the report is new to the Vendor, it
    MUST transition $q^{cs} \xrightarrow{\mathbf{V}}Vfd\cdot\cdot\cdot$.

!!! note "[RMB-02](../../reference/specs/protocol.md#rmb-02) — [RMB-06](../../reference/specs/protocol.md#rmb-06)"

    Any $R*$ message, aside from $RS$, received by recipient in
    $q^{rm} \in S$ is an error because it indicates the sender thought
    the receiver was aware of a report they had no knowledge of. The
    Recipient SHOULD respond with both an $RE$ to signal the error and
    $GI$ to find out what the sender expected.

!!! note "[RMB-07](../../reference/specs/protocol.md#rmb-07)"

    Recipients SHOULD acknowledge $RE$ messages ($RK$) and inquire
    ($GI$) as to the nature of the error.

!!! note inline end "RM Messages Sent and State Transitions"

    $$S_i \times M_{ij}^{rm} \rightarrow S_i$$

### RM Messages Sent and State Transitions

The table below lists each RM message type and the states in which that message is appropriate to send along with the
corresponding sender state transition.

| Sender Preconditions<br/>$s_n \in S_i$<br/>$q^{rm},q^{em},q^{cs}$ | Transition<br/>$(s_n \xrightarrow{} s_{n+1})$<br/>$q^{rm},q^{em},q^{cs}$ | Message Type<br/>$\rightharpoonup$<br/>$M_{ij}$ |
|:-----------------------------------------------------------------:|:------------------------------------------------------------------------:|:-------------------------------------------------------:|
| $A,*,*$ | $-,-,-$ |                          $RS$                           |
| $R,*,*$ | $\xrightarrow{i} I,-,-$ |                          $RI$                           |
| $\{R,I\},*,*$ | $\xrightarrow{v} V,-,-$ |                          $RV$                           |
| $\{V,A\},*,*$ | $\xrightarrow{d} D,-,-$ |                          $RD$                           |
| $\{V,D\},*,*$ | $\xrightarrow{a} A,-,-$ |                          $RA$                           |
| $\{I,D,A\},*,*$ | $\xrightarrow{c} C,-,-$ |                          $RC$                           |
| $*,*,*$ | $-,-,-$ |                          $RE$                           |
| $*,*,*$ | $-,-,-$ |                          $RK$                           |

!!! note inline end "RM Messages Received and State Transitions"

    $$S_i \times M_{ji}^{rm} \rightarrow S_i$$

### RM Messages Received and State Transitions

The table below lists the effects of receiving RM messages on the receiving Participant's state coupled with the
expected response message.

| Received Msg.<br/>$\leftharpoondown$<br/>$M_{ji}$ | Receiver Precondition<br/>$s_n \in S_i$<br/>$q^{rm},q^{em},q^{cs}$ | Receiver Transition<br/>$(s_n \xrightarrow{} s_{n+1})$<br/>$q^{rm},q^{em},q^{cs}$ | Response Msg.<br/>$\rightharpoonup$<br/>$M_{ij}$ |
|:-------------------------------------------------:|:------------------------------------------------------------------:|:---------------------------------------------------------------------------------:|:------------------------------------------------:|
|                        $*$                        | $C,*,*$ | $-,-,-$ |                       $-$                        |
|                       $RS$                        | $S,*,vfd \cdot\cdot\cdot$ | $\xrightarrow{r} R,-,\xrightarrow{\mathbf{V}} Vfd \cdot\cdot\cdot$ |               $RK$, $CV$ (vendor)                |
|                       $RS$                        | $\{ R, I, V,D,A\},*,vfd \cdot\cdot\cdot$ | $-,-,\xrightarrow{\mathbf{V}} Vfd \cdot\cdot\cdot$ |               $RK$, $CV$ (vendor)                |
|                       $RS$                        | $S,*,V \cdot\cdot\cdot\cdot\cdot$ | $\xrightarrow{r} R,-,-$ |               $RK$, $CV$ (vendor)                |
|                       $RS$                        | $\{ R, I, V,D,A\},*,V \cdot\cdot\cdot\cdot\cdot$ | $-,-,-$ |               $RK$, $CV$ (vendor)                |
|                       $RS$                        | $S,*,*$ | $\xrightarrow{r} R,-,-$ |                $RK$ (non-vendor)                 |
|                       $RS$                        | $\{ R, I, V,D,A\},*,*$ | $-,-,-$ |                $RK$ (non-vendor)                 |
|               $\{RI,RV,RD,RA,RC\}$                | $\{R,I,V,D,A\},*,*$ | $-,-,-$ |                       $RK$                       |
|               $\{RI,RV,RD,RA,RC\}$                | $S,*,*$ | $-,-,-$ |                    $RE + GI$                     |
|                       $RE$                        | $*,*,*$ | $-,-,-$ |                    $RK + GI$                    |
|                       $RK$                        | $*,*,*$ | $-,-,-$ |                       $-$                        |

## EM Transition Functions

The appropriate Participant behavior in the EM process depends on whether the case state
$q^{cs}$ is in $\cdot\cdot\cdot pxa$ or not.

!!! note "[EMB-01](../../reference/specs/protocol.md#emb-01) — [EMB-02](../../reference/specs/protocol.md#emb-02)"

    Participants SHALL NOT negotiate embargoes where the vulnerability
    or its exploit is public or attacks are known to have occurred.

!!! note "[CM-12](../../reference/specs/protocol.md#cm-12), [EP-04](../../reference/specs/protocol.md#ep-04)"

    Embargo management begins when the case is created, not before.
    A sender that wants particular embargo terms states them with the report ($RS$).
    An embargo-eligible case begins with an active embargo: the shorter of the sender's terms and the receiver's published default, or the protocol default when neither applies.
    Therefore, an $E*$ message about a report the Recipient does not know of ($q^{rm} \in S$) is an error, just as an $R*$ message other than $RS$ is.
    The receiver table below answers it the way it answers an unexpected $R*$ message: with $EE$ to signal the error and $GI$ to find out what the sender expected.
    [A Protocol Default Embargo Replaces the Pre-Case Phase](../../adr/0096-protocol-default-embargo.md) records why there is no pre-case embargo negotiation.

!!! note "[EMB-06](../../reference/specs/protocol.md#emb-06)"

    Participants MAY reject any embargo proposals or revisions for any
    reason.

!!! note "[EMB-13](../../reference/specs/protocol.md#emb-13)"

    If information about the vulnerability or an exploit for it has been
    made public, Participants SHALL terminate the embargo
    ($q^{cs} \in \{\cdot\cdot\cdot P \cdot\cdot, \cdot\cdot\cdot\cdot X \cdot\}$).

!!! note "[EMB-13](../../reference/specs/protocol.md#emb-13)"

    If attacks are known to have occurred, Participants SHOULD terminate
    the embargo ($q^{cs} \in \cdot\cdot\cdot\cdot\cdot A$).

!!! note "[EMB-01](../../reference/specs/protocol.md#emb-01) — [EMB-07](../../reference/specs/protocol.md#emb-07)"

    Participants SHOULD send $EK$ in acknowledgment of any other $E*$
    message except $EK$ itself.

!!! note "[EMB-08](../../reference/specs/protocol.md#emb-08)"

    Participants SHOULD acknowledge ($EK$) and inquire ($GI$) about the
    nature of any error reported by an incoming $EE$ message.

!!! note inline end "EM Messages Sent and State Transitions"

    $$S_i \times M_{ij}^{em} \rightarrow S_i$$

### EM Messages Sent and State Transitions

The following table lists each EM message type and the states in which that message is appropriate to send along with
the corresponding sender state transition.

| Sender Precondition<br/>$(s_n \in S_i)$<br/>$q^{rm},q^{em},q^{cs}$ | Sender Transition<br/>$(s_n \xrightarrow{} s_{n+1})$<br/>$q^{rm},q^{em},q^{cs}$ | Message Type<br/>$\rightharpoonup$<br/>$M_{ij}$ |
|:-------------------------------------------------------------------:|:--------------------------------------------------------------------------------:|:-----------------------------------------------:|
| $\lnot \{S,C\},N,\cdot\cdot\cdot pxa$ | $-,\xrightarrow{p} P,-$ |                      $EP$                       |
| $\lnot \{S,C\},P,\cdot\cdot\cdot pxa$ | $-,\xrightarrow{p} P,-$ |                      $EP$                       |
| $\lnot \{S,C\},P,\cdot\cdot\cdot pxa$ | $-,\xrightarrow{a} A,-$ |                      $EA$                       |
| $\lnot \{S,C\},A,\cdot\cdot\cdot pxa$ | $-,\xrightarrow{p} R,-$ |                      $EV$                       |
| $\lnot \{S,C\},R,\cdot\cdot\cdot pxa$ | $-,\xrightarrow{p} R,-$ |                      $EV$                       |
| $\lnot \{S,C\},R,\cdot\cdot\cdot pxa$ | $-,\xrightarrow{r} A,-$ |                      $EJ$                       |
| $\lnot \{S,C\},R,\cdot\cdot\cdot pxa$ | $-,\xrightarrow{a} A,-$ |                      $EC$                       |
| $\lnot \{S,C\},P,*$ | $-,\xrightarrow{r} N,-$ |                      $ER$                       |
| $\lnot \{S,C\},A,*$ | $-,\xrightarrow{t} X,-$ |                      $ET$                       |
| $\lnot \{S,C\},R,*$ | $-,\xrightarrow{t} X,-$ |                      $ET$                       |
| $\lnot C,*,*$ | $-,-,-$ |                      $EK$                       |
| $\lnot C,*,*$ | $-,-,-$ |                      $EE$                       |

A Participant still in RM *Start* has no case to negotiate, so the only EM messages it sends are $EE$, the error it returns when an EM message reaches it before the report does, and $EK$, its acknowledgement of an $EE$.

!!! note inline end "EM Messages Received and State Transitions"

    $$S_i \times M_{ji}^{em} \rightarrow S_i$$

### EM Messages Received and State Transitions

The next table lists the effects of receiving an EM message to the receiving Participant's state, grouped by the EM message type received.

!!! tip "Notes on Embargo Messages Received and State Transitions"

    Incoming EM Messages do not trigger any change in $q^{cs}$ or $q^{rm}$.
    When CS is $q^{cs} \not \in  \cdot\cdot\cdot pxa$, embargoes are not viable.

| Received Msg.<br/>$\leftharpoondown$<br/>$M_{ji}$ | Receiver Precondition<br/>$s_n \in S_i$<br/>$q^{rm},q^{em},q^{cs}$ | Receiver Transition<br/>$(s_n \xrightarrow{} s_{n+1})$<br/>$q^{rm},q^{em},q^{cs}$ | Response Msg.<br/>$\rightharpoonup$<br/>$M_{ij}$ |
|:--------------------------------------------------------:|:-----------------------------------------------------------:|:---------------------------------------------------------------------------------:|:------------------------------------------------:|
|                           $EP$                           | $\lnot \{S,C\},N,\cdot\cdot\cdot pxa$ | $-,\xrightarrow{p} P,-$ |                       $EK$                       |
|                           $EP$                           | $\lnot \{S,C\},P,\cdot\cdot\cdot pxa$ | $-,-,-$ |                       $EK$                       |
|                           $EA$                           | $\lnot \{S,C\},P,\cdot\cdot\cdot pxa$ | $-,\xrightarrow{a} A,-$ |                       $EK$                       |
|                           $EV$                           | $\lnot \{S,C\},A,\cdot\cdot\cdot pxa$ | $-,\xrightarrow{p} R,-$ |                       $EK$                       |
|                           $EV$                           | $\lnot \{S,C\},R,\cdot\cdot\cdot pxa$ | $-,-,-$ |                       $EK$                       |
|                           $EJ$                           | $\lnot \{S,C\},R,\cdot\cdot\cdot pxa$ | $-,\xrightarrow{r} A,-$ |                       $EK$                       |
|                           $EC$                           | $\lnot \{S,C\},R,\cdot\cdot\cdot pxa$ | $-,\xrightarrow{a} A,-$ |                       $EK$                       |
|                           $ER$                           | $\lnot \{S,C\},P,*$ | $-,\xrightarrow{r} N,-$ |                       $EK$                       |
|                           $ET$                           | $\lnot \{S,C\},A,*$ | $-,\xrightarrow{t} X,-$ |                       $EK$                       |
|                           $ET$                           | $\lnot \{S,C\},R,*$ | $-,\xrightarrow{t} X,-$ |                       $EK$                       |
|                           $ET$                           | $\lnot \{S,C\},X,*$ | $-,-,-$ |                       $EK$                       |
|                           $EP$                           | $\lnot \{S,C\},N,\lnot \cdot\cdot\cdot pxa$ | $-,-,-$ |                       $ER$                       |
|                           $EP$                           | $\lnot \{S,C\},P,\lnot \cdot\cdot\cdot pxa$ | $-,\xrightarrow{r} N,-$ |                       $ER$                       |
|                           $EA$                           | $\lnot \{S,C\},P,\lnot \cdot\cdot\cdot pxa$ | $-,\xrightarrow{r} N,-$ |                       $ER$                       |
|                           $EV$                           | $\lnot \{S,C\},A,\lnot \cdot\cdot\cdot pxa$ | $-,\xrightarrow{t} X,-$ |                       $ET$                       |
|                           $EV$                           | $\lnot \{S,C\},R,\lnot \cdot\cdot\cdot pxa$ | $-,\xrightarrow{t} X,-$ |                       $ET$                       |
|                           $EJ$                           | $\lnot \{S,C\},R,\lnot \cdot\cdot\cdot pxa$ | $-,\xrightarrow{t} X,-$ |                       $ET$                       |
|                           $EC$                           | $\lnot \{S,C\},R,\lnot \cdot\cdot\cdot pxa$ | $-,\xrightarrow{t} X,-$ |                       $ET$                       |
|           $\{EP,EA,EV,EJ,EC,ER,ET\}$           | $S,*,*$ | $-,-,-$ |                     $EE+GI$                      |
|                           $EE$                           | $\lnot C,*,*$ | $-,-,-$ |                     $EK+GI$                      |
|                           $EK$                           | $\lnot C,*,*$ | $-,-,-$ |                       $-$                        |
|           Any EM msg. not<br/> addressed above           | $\lnot C,*,*$ | $-,-,-$ |                       $EE$                       |

## CVD Transition Functions

!!! tip inline end "Participant-Specific State Messages Promote Shared Situation Awareness"

    Effective coordination is usually improved with Participants' mutual awareness of each other's state.

The Vendor-specific portions of the CS (*Vendor Awareness*, *Fix Ready*, and
*Fix Deployed*) are per-Participant states.
Therefore, the receiver of a message indicating another Participant has changed their $\{v,V\}$, $\{f,F\}$ or $\{d,D\}$
status is not expected to change their own state as a result.

However, this is not the case for the remainder of the CS substates.
As above, the appropriate Participant response to receiving CS messages (namely, those surrounding *Public Awareness*,
*Exploit Public*, or *Attacks Observed*) depends on the state of the EM process.

!!! note "[CSB-12](../../reference/specs/protocol.md#csb-12) — [CSB-13](../../reference/specs/protocol.md#csb-13)"

    Participants SHALL initiate embargo termination upon becoming aware
    of publicly available information about the vulnerability or its
    exploit code.

!!! note "[CSB-14](../../reference/specs/protocol.md#csb-14)"

    Participants SHOULD initiate embargo termination upon becoming aware
    of attacks against an otherwise unpublished vulnerability.

!!! note inline end "CS Messages Sent and State Transitions"

    $$S_i \times M_{ij}^{cs} \rightarrow S_i$$

### CS Messages Sent and State Transitions

The following table lists each CVD message type and the states in which that message is appropriate to send along with
the corresponding sender state transition.

!!! tip "Notes on CS Messages Sent and State Transitions"

    Note that when a CS message induces a $q^{rm}$ or $q^{em}$ state change, the corresponding RM or EM message should 
    be sent as indicated in the tables above.

| Sender Precondition<br/>$(s_n \in S_i)$<br/>$q^{rm},q^{em},q^{cs}$ | Sender Transition<br/>$(s_n \xrightarrow{} s_{n+1})$<br/>$q^{rm},q^{em},q^{cs}$ | Message Type<br/>$\rightharpoonup$<br/>$M_{ij}$ |
|:------------------------------------------------------------------:|:-------------------------------------------------------------------------------:|:-----------------------------------------------:|
| $S,*,vfd \cdot\cdot\cdot$ | $\xrightarrow{r} R,-,\xrightarrow{\mathbf{V}} Vfd \cdot\cdot\cdot$ |                      $CV$                       |
| $\lnot C,*,Vfd \cdot\cdot\cdot$ | $-,-,\xrightarrow{\mathbf{F}} VFd \cdot\cdot\cdot$ |                      $CF$                       |
| $\lnot C,*,VFd \cdot\cdot\cdot$ | $-,-,\xrightarrow{\mathbf{D}} VFD \cdot\cdot\cdot$ |                      $CD$                       |
| $\lnot C,\{N,X\},\cdot\cdot\cdot p \cdot\cdot$ | $-,-,\xrightarrow{\mathbf{P}} \cdot\cdot\cdot P \cdot\cdot$ |                      $CP$                       |
| $\lnot C,P,\cdot\cdot\cdot p \cdot\cdot$ | $-,\xrightarrow{r} N,\xrightarrow{\mathbf{P}} \cdot\cdot\cdot P \cdot\cdot$ |                      $CP$                       |
| $\lnot C,\{A,R\},\cdot\cdot\cdot p \cdot\cdot$ | $-,\xrightarrow{t} X,\xrightarrow{\mathbf{P}} \cdot\cdot\cdot P \cdot\cdot$ |                      $CP$                       |
| $\lnot C,\{N,X\},\cdot\cdot\cdot px \cdot$ | $-,-,\xrightarrow{\mathbf{X+P}} \cdot\cdot\cdot PX \cdot$ |                     $CX+CP$                     |
| $\lnot C,P,\cdot\cdot\cdot px \cdot$ | $-,\xrightarrow{r} N,\xrightarrow{\mathbf{X+P}} \cdot\cdot\cdot PX \cdot$ |                     $CX+CP$                     |
| $\lnot C,\{A,R\},\cdot\cdot\cdot px \cdot$ | $-,\xrightarrow{t} X,\xrightarrow{\mathbf{X+P}} \cdot\cdot\cdot PX \cdot$ |                     $CX+CP$                     |
| $\lnot C,\{N,X\},\cdot\cdot\cdot Px \cdot$ | $-,-,\xrightarrow{\mathbf{X}} \cdot\cdot\cdot PX \cdot$ |                      $CX$                       |
| $\lnot C,P,\cdot\cdot\cdot Px \cdot$ | $-,\xrightarrow{r} N,\xrightarrow{\mathbf{X}} \cdot\cdot\cdot PX \cdot$ |                      $CX$                       |
| $\lnot C,\{A,R\},\cdot\cdot\cdot Px \cdot$ | $-,\xrightarrow{t} X,\xrightarrow{\mathbf{X}} \cdot\cdot\cdot PX \cdot$ |                      $CX$                       |
| $\lnot C,\{N,X\},\cdot\cdot\cdot\cdot\cdot a$ | $-,-,\xrightarrow{\mathbf{A}} \cdot\cdot\cdot\cdot\cdot A$ |                      $CA$                       |
| $\lnot C,P,\cdot\cdot\cdot\cdot\cdot a$ | $-,\xrightarrow{r} N,\xrightarrow{\mathbf{A}} \cdot\cdot\cdot\cdot\cdot A$ |                      $CA$                       |
| $\lnot C,\{A,R\},\cdot\cdot\cdot\cdot\cdot a$ | $-,\xrightarrow{t} X,\xrightarrow{\mathbf{A}} \cdot\cdot\cdot\cdot\cdot A$ |                      $CA$                       |

!!! note inline end "CS Messages Received and State Transitions"

    $$S_i \times M_{ji}^{cs} \rightarrow S_i$$

### CS Messages Received and State Transitions

The following table lists the effects of receiving a
CS message to the receiving Participant's state coupled with the expected response message.

| Received Msg.<br/>$\leftharpoondown$<br/>$M_{ji}$ | Receiver Precondition<br/>$s_n \in S_i$<br/>$q^{rm},q^{em},q^{cs}$ | Receiver Transition<br/>$(s_n \xrightarrow{} s_{n+1})$<br/>$q^{rm},q^{em},q^{cs}$ | Response Msg.<br/>$\rightharpoonup$<br/>$M_{ij}$ |
|:-------------------------------------------------:|:------------------------------------------------------------------:|:---------------------------------------------------------------------------------:|:------------------------------------------------:|
|                       $CV$                        | $\lnot C,*,*$ | $-,-,-$ |                       $CK$                       |
|                       $CF$                        | $\lnot C,*,*$ | $-,-,-$ |                       $CK$                       |
|                       $CD$                        | $\lnot C,*,*$ | $-,-,-$ |                       $CK$                       |
|                       $CP$                        | $\lnot C,P,\cdot\cdot\cdot p \cdot\cdot$ | $-,\xrightarrow{r} N,\xrightarrow{\mathbf{P}} \cdot\cdot\cdot P \cdot\cdot$ |                       $CK$                       |
|                       $CP$                        | $\lnot C,\{A,R\},\cdot\cdot\cdot p \cdot\cdot$ | $-,\xrightarrow{t} X,\xrightarrow{\mathbf{P}} \cdot\cdot\cdot P \cdot\cdot$ |                       $CK$                       |
|                       $CP$                        | $\lnot C,\{N,X\},\cdot\cdot\cdot p \cdot\cdot$ | $-,-,\xrightarrow{\mathbf{P}} \cdot\cdot\cdot P \cdot\cdot$ |                       $CK$                       |
|                       $CP$                        | $\lnot C,*,\cdot\cdot\cdot P \cdot\cdot$ | $-,-,-$ |                       $CK$                       |
|                       $CX$                        | $\lnot C,P,\cdot\cdot\cdot px \cdot$ | $-,\xrightarrow{r} N,\xrightarrow{\mathbf{X+P}} \cdot\cdot\cdot PX \cdot$ |                       $CK$                       |
|                       $CX$                        | $\lnot C,\{A,R\},\cdot\cdot\cdot px \cdot$ | $-,\xrightarrow{t} X,\xrightarrow{\mathbf{X+P}} \cdot\cdot\cdot PX \cdot$ |                       $CK$                       |
|                       $CX$                        | $\lnot C,\{N,X\},\cdot\cdot\cdot px \cdot$ | $-,-,\xrightarrow{\mathbf{X+P}} \cdot\cdot\cdot PX \cdot$ |                       $CK$                       |
|                       $CX$                        | $\lnot C,*,\cdot\cdot\cdot Px \cdot$ | $-,-,\xrightarrow{\mathbf{X}} \cdot\cdot\cdot PX \cdot$ |                       $CK$                       |
|                       $CX$                        | $\lnot C,*,\cdot\cdot\cdot PX \cdot$ | $-,-,-$ |                       $CK$                       |
|                       $CA$                        | $\lnot C,P,\cdot\cdot\cdot p \cdot a$ | $-,\xrightarrow{r} N,\xrightarrow{\mathbf{A}} \cdot\cdot\cdot P \cdot A$ |                       $CK$                       |
|                       $CA$                        | $\lnot C,\{A,R\},\cdot\cdot\cdot p \cdot a$ | $-,\xrightarrow{t} X,\xrightarrow{\mathbf{A}} \cdot\cdot\cdot P \cdot A$ |                       $CK$                       |
|                       $CA$                        | $\lnot C,\{N,X\},\cdot\cdot\cdot p \cdot a$ | $-,-,\xrightarrow{\mathbf{A}} \cdot\cdot\cdot P \cdot A$ |                       $CK$                       |
|                       $CA$                        | $\lnot C,*,\cdot\cdot\cdot P \cdot a$ | $-,-,\xrightarrow{\mathbf{A}} \cdot\cdot\cdot P \cdot A$ |                       $CK$                       |
|                       $CA$                        | $\lnot C,*,\cdot\cdot\cdot\cdot\cdot A$ | $-,-,-$ |                       $CK$                       |
| $CE$ | $\lnot C,*,*$ | $-,-,-$ |                     $CK+GI$                      |
| $CK$ | $\lnot C,*,*$ | $-,-,-$ |                       $-$                        |

## General Transition Functions

Finally, for the sake of completeness, general inquiries, acknowledgments, and errors are otherwise independent
of the rest of the processes.
No state changes are expected to occur based on the receipt of a General message.

!!! tip "General Messages are not a *No-Op*"

    This does not imply that the *content* of a general message has no effect on the progression 
    of a case, merely that the act of sending or receiving a general message itself does not imply any necessary protocol
    state change to either the sender or receiver Participants.

!!! note inline end "General Messages Sent and State Transitions"

    $$S_i \times M_{ij}^{gen} \rightarrow S_i$$

### General Messages Sent and State Transitions

The following table lists each general message and the states in which it is appropriate to send along with the
corresponding sender state.

| Sender Precondition<br/>$(s_n \in S_i)$<br/>$q^{rm},q^{em},q^{cs}$ | Sender Transition<br/>$(s_n \xrightarrow{} s_{n+1})$<br/>$q^{rm},q^{em},q^{cs}$ | Message Type<br/>$\rightharpoonup$<br/>$M_{ij}$ |
|:------------------------------------------------------------------:|:-------------------------------------------------------------------------------:|:-----------------------------------------------:|
| $*,*,*$ | $-,-,-$ |                      $GI$                       |
| $*,*,*$ | $-,-,-$ |                      $GK$                       |
| $*,*,*$ | $-,-,-$ |                      $GE$                       |

!!! note inline end "General Messages Received and State Transitions"

    $$S_i \times M_{ji}^{gen} \rightarrow S_i$$

### General Messages Received and State Transitions

The next table lists the effects of receiving a general message to the receiving Participant's state coupled with the
expected response message.

| Received Msg.<br/>$\leftharpoondown$<br/>$M_{ji}$ | Receiver Precondition<br/>$s_n \in S_i$<br/>$q^{rm},q^{em},q^{cs}$ | Receiver Transition<br/>$(s_n \xrightarrow{} s_{n+1})$<br/>$q^{rm},q^{em},q^{cs}$ | Response Msg.<br/>$\rightharpoonup$<br/>$M_{ij}$ |
|:-------------------------------------------------:|:------------------------------------------------------------------:|:---------------------------------------------------------------------------------:|:------------------------------------------------:|
|                      $GI$                        | $*,*,*$ | $-,-,-$ |                       $GK$                       |
|                      $GK$                        | $*,*,*$ | $-,-,-$ |                       $-$                        |
|                      $GE$                        | $*,*,*$ | $-,-,-$ |                       $GI$                       |
