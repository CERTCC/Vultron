# Transition Functions {#sec:protocol_transition_functions}

{% include-markdown "../../includes/normative.md" %}

In this section, we describe the transition functions for the RM, EM, and CVD Case processes, respectively.
Note that while the RM process is largely independent of the other two process models, the EM and CVD process models 
have some noteworthy interactions, which we will cover in detail.

Revisiting the formal protocol definition from the [introduction](index.md): 

!!! note "Transition Function Defined"

    $succ$ is a partial function mapping for each $i$ and $j$,
    
    $$S_i \times M_{ij} \rightarrow S_i \textrm{ and } S_i \times M_{ji} \rightarrow S_i$$

    $succ(s,x)$ is the state entered after a process transmits or receives
    message $x$ in state $s$. It is a transmission if $x$ is from $M_{ij}$
    and a reception if $x$ is from $M_{ji}$.


!!! tip "Notation Conventions on this Page"

    - By convention, CS states are labeled in the order $vfdpxa$.
    - Participant state is a tuple of the individual CS, RM, and EM states $S_i = (q^{cs}, q^{rm}, q^{em})$.
    - Dots ($\cdot$) in states indicate single wildcards.
    For example, $Vfd \cdot\cdot\cdot$ includes $Vfdpxa, VfdPxA, VfdPXA,\dots$
    - Asterisks ($*$) indicate arbitrary wildcards.
    - Dashes ($−$) indicate no state change.
    - Left-harpoons ($\leftharpoondown$) indicate a message received.
    - Right-harpoons ($\rightharpoonup$) indicate a message sent.


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

!!! note inline end "RM Messages Sent and State Transitions"
    
    $$S_i \times M_{ij}^{rm} \rightarrow S_i$$

### RM Messages Sent and State Transitions

The table below lists each RM message type and the states in which that message is appropriate to send along with the
corresponding sender state transition.


| Sender Preconditions<br/>$s_n \in S_i$<br/>$q^{cs},q^{rm},q^{em}$ | Transition<br/>$(s_n \xrightarrow{} s_{n+1})$<br/>$q^{cs},q^{rm},q^{em}$ | Message Type<br/>$\rightharpoonup$<br/>$M_{ij}$ |
|:-----------------------------------------------------------------:|:------------------------------------------------------------------------:|:-------------------------------------------------------:|
| $*,A,*$                                                           | $-, -, -$                                                                |                          $RS$                           |
| $*,\{R,V\},*$                                                     | $-, \xrightarrow{i} I, -$                                                |                          $RI$                           |
| $*,\{R,I\},*$                                                     | $-, \xrightarrow{v} V, -$                                                |                          $RV$                           |
| $*,\{V,A\},*$                                                     | $-, \xrightarrow{d} D, -$                                                |                          $RD$                           |
| $*,\{V,D\},*$                                                     | $-, \xrightarrow{a} A, -$                                                |                          $RA$                           |
| $*,\{I,D,A\},*$                                                   | $-, \xrightarrow{c} C, -$                                                |                          $RC$                           |
| $*,*,*$                                              | $-, -, -$                                              |                          $RE$                           |
| $*,*,*$                                              | $-, -, -$                                              |                          $RK$                           |


!!! note inline end "RM Messages Received and State Transitions"

    $$S_i \times M_{ji}^{rm} \rightarrow S_i$$

### RM Messages Received and State Transitions

The table below lists the effects of receiving RM messages on the receiving Participant's state coupled with the 
expected response message.


| Received Msg.<br/>$\leftharpoondown$<br/>$M_{ji}$ | Receiver Precondition<br/>$s_n \in S_i$<br/>$q^{cs},q^{rm},q^{em}$ | Receiver Transition<br/>$(s_n \xrightarrow{} s_{n+1})$<br/>$q^{cs},q^{rm},q^{em}$ | Response Msg.<br/>$\rightharpoonup$<br/>$M_{ij}$ |
|:-------------------------------------------------:|:------------------------------------------------------------------:|:---------------------------------------------------------------------------------:|:------------------------------------------------:|
|                        $*$                        |                              $*,C,*$                               |                                      $-,-,-$                                      |                       $-$                        |
|                       $RS$                        |                     $vfd \cdot\cdot\cdot,S,*$                      |         $\xrightarrow{\mathbf{V}} Vfd \cdot\cdot\cdot, \xrightarrow{r} R,-$         |               $RK$, $CV$ (vendor)                |
|                       $RS$                        |              $vfd \cdot\cdot\cdot,\{ R, I, V,D,A\},*$              |                 $\xrightarrow{\mathbf{V}} Vfd \cdot\cdot\cdot,-,-$                  |               $RK$, $CV$ (vendor)                |
|                       $RS$                        |                 $V \cdot\cdot\cdot\cdot\cdot,S,*$                  |                               $-,\xrightarrow{r} R,-$                               |               $RK$, $CV$ (vendor)                |
|                       $RS$                        |          $V \cdot\cdot\cdot\cdot\cdot,\{ R, I, V,D,A\},*$          |                                       $-,-,-$                                       |               $RK$, $CV$ (vendor)                |
|                       $RS$                        |                              $*,S,*$                               |                               $-,\xrightarrow{r} R,-$                               |                $RK$ (non-vendor)                 |
|                       $RS$                        |                       $*,\{ R, I, V,D,A\},*$                       |                                       $-,-,-$                                       |                $RK$ (non-vendor)                 |
|               $\{RI,RV,RD,RA,RC\}$                |                        $*,\{R,I,V,D,A\},*$                         |                                       $-,-,-$                                       |                       $RK$                       |
|               $\{RI,RV,RD,RA,RC\}$                |                              $*,S,*$                               |                                       $-,-,-$                                       |                    $RE + GI$                     |
|                       $RE$                        |                              $*,*,*$                               |                                       $-,-,-$                                       |                    $RK$ + GI$                    |
|                       $RK$                        |                              $*,*,*$                               |                                       $-,-,-$                                       |                       $-$                        |

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


!!! note inline end "EM Messages Sent and State Transitions"
    
    $$S_i \times M_{ij}^{em} \rightarrow S_i$$


### EM Messages Sent and State Transitions

The following table lists each EM message type and the states in which that message is appropriate to send along with
the corresponding sender state transition.

| Sender Precondition<br/>$(s_n \in S_i)$<br/>$q^{cs},q^{rm},q^{em}$ | Sender Transition<br/>$(s_n \xrightarrow{} s_{n+1})$<br/>$q^{cs},q^{rm},q^{em}$ | Message Type<br/>$\rightharpoonup$<br/>$M_{ij}$ |
|:-------------------------------------------------------------------:|:--------------------------------------------------------------------------------:|:-----------------------------------------------:|
|                   $\cdot\cdot\cdot pxa,\lnot C,N$                   |                             $-,-,\xrightarrow{p} P$                              |                      $EP$                       |
|                   $\cdot\cdot\cdot pxa,\lnot C,P$                   |                             $-,-,\xrightarrow{p} P$                              |                      $EP$                       |
|                   $\cdot\cdot\cdot pxa,\lnot C,P$                   |                             $-,-,\xrightarrow{a} A$                              |                      $EA$                       |
|                   $\cdot\cdot\cdot pxa,\lnot C,A$                   |                             $-,-,\xrightarrow{p} R$                              |                      $EV$                       |
|                   $\cdot\cdot\cdot pxa,\lnot C,R$                   |                             $-,-,\xrightarrow{p} R$                              |                      $EV$                       |
|                   $\cdot\cdot\cdot pxa,\lnot C,R$                   |                             $-,-,\xrightarrow{r} A$                              |                      $EJ$                       |
|                   $\cdot\cdot\cdot pxa,\lnot C,R$                   |                             $-,-,\xrightarrow{a} A$                              |                      $EC$                       |
|                            $*,\lnot C,P$                            |                             $-,-,\xrightarrow{r} N$                              |                      $ER$                       |
|                            $*,\lnot C,A$                            |                             $-,-,\xrightarrow{t} X$                              |                      $ET$                       |
|                            $*,\lnot C,R$                            |                             $-,-,\xrightarrow{t} X$                              |                      $ET$                       |
|                            $*,\lnot C,*$                            |                                     $-,-,-$                                      |                      $EK$                       |
|                            $*,\lnot C,*$                            |                                     $-,-,-$                                      |                      $EE$                       |


!!! note inline end "EM Messages Received and State Transitions"

    $$S_i \times M_{ji}^{em} \rightarrow S_i$$

### EM Messages Received and State Transitions

The next table lists the effects of receiving an EM message to the receiving Participant's state, grouped by the EM message type received.

!!! tip "Notes on Embargo Messages Received and State Transitions"

    Incoming EM Messages do not trigger any change in $q^{cs}$ or $q^{rm}$.
    When CS is $q^{cs} \not \in  \cdot\cdot\cdot pxa$, embargoes are not viable.


| Received Msg.<br/>$\leftharpoondown$<br/>$M_{ji}$ | Receiver Precondition<br/>$s_n \in S_i$<br/>$q^{cs},q^{rm}$ | Receiver Transition<br/>$(s_n \xrightarrow{} s_{n+1})$<br/>$q^{cs},q^{rm},q^{em}$ | Response Msg.<br/>$\rightharpoonup$<br/>$M_{ij}$ |
|:--------------------------------------------------------:|:-----------------------------------------------------------:|:---------------------------------------------------------------------------------:|:------------------------------------------------:|
|                           $EP$                           |              $\cdot\cdot\cdot pxa, \lnot C, N$              |                              $-,-,\xrightarrow{p} P$                              |                       $EK$                       |
|                           $EP$                           |              $\cdot\cdot\cdot pxa, \lnot C, P$              |                                      $-,-,-$                                      |                       $EK$                       |
|                           $EA$                           |              $\cdot\cdot\cdot pxa, \lnot C, P$              |                              $-,-,\xrightarrow{a} A$                              |                       $EK$                       |
|                           $EV$                           |              $\cdot\cdot\cdot pxa, \lnot C, A$              |                              $-,-,\xrightarrow{p} R$                              |                       $EK$                       |
|                           $EV$                           |              $\cdot\cdot\cdot pxa, \lnot C, R$              |                                      $-,-,-$                                      |                       $EK$                       |
|                           $EJ$                           |              $\cdot\cdot\cdot pxa, \lnot C, R$              |                              $-,-,\xrightarrow{r} A$                              |                       $EK$                       |
|                           $EC$                           |              $\cdot\cdot\cdot pxa, \lnot C, R$              |                              $-,-,\xrightarrow{a} A$                              |                       $EK$                       |
|                           $ER$                           |                       $*, \lnot C, P$                       |                              $-,-,\xrightarrow{r} N$                              |                       $EK$                       |
|                           $ET$                           |                       $*, \lnot C, A$                       |                              $-,-,\xrightarrow{t} X$                              |                       $EK$                       |
|                           $ET$                           |                       $*, \lnot C, R$                       |                              $-,-,\xrightarrow{t} X$                              |                       $EK$                       | 
|                           $ET$                           |                       $*, \lnot C, X$                       |                                      $-,-,-$                                      |                       $EK$                       |
|                           $EP$                           |           $\lnot \cdot\cdot\cdot pxa,\lnot C, N$            |                                      $-,-,-$                                      |                       $ER$                       |
|                           $EP$                           |           $\lnot \cdot\cdot\cdot pxa,\lnot C, P$            |                              $-,-,\xrightarrow{r} N$                              |                       $ER$                       |
|                           $EA$                           |           $\lnot \cdot\cdot\cdot pxa,\lnot C, P$            |                              $-,-,\xrightarrow{r} N$                              |                       $ER$                       |
|                           $EV$                           |           $\lnot \cdot\cdot\cdot pxa,\lnot C, A$            |                              $-,-,\xrightarrow{t} X$                              |                       $ET$                       |
|                           $EV$                           |           $\lnot \cdot\cdot\cdot pxa,\lnot C, R$            |                              $-,-,\xrightarrow{t} X$                              |                       $ET$                       |
|                           $EJ$                           |           $\lnot \cdot\cdot\cdot pxa,\lnot C, R$            |                              $-,-,\xrightarrow{t} X$                              |                       $ET$                       |
|                           $EC$                           |           $\lnot \cdot\cdot\cdot pxa,\lnot C, R$            |                              $-,-,\xrightarrow{t} X$                              |                       $ET$                       |
|                           $EE$                           |                       $*,\lnot C,*$                       |                                      $-,-,-$                                      |                     $EK+GI$                      |
|                           $EK$                           |                       $*,\lnot C,*$                       |                                      $-,-,-$                                      |                       $-$                        |
|           Any EM msg. not<br/> addressed above           |                       $*,\lnot C,*$                       |                                      $-,-,-$                                      |                       $EE$                       |


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

!!! note inline end "CS Messages Sent and State Transitions"
    
    $$S_i \times M_{ij}^{cs} \rightarrow S_i$$

### CS Messages Sent and State Transitions

The following table lists each CVD message type and the states in which that message is appropriate to send along with
the corresponding sender state transition.



!!! tip "Notes on CS Messages Sent and State Transitions"

    Note that when a CS message induces a $q^{rm}$ or $q^{em}$ state change, the corresponding RM or EM message should 
    be sent as indicated in the tables above.


| Sender Precondition<br/>$(s_n \in S_i)$<br/>$q^{cs},q^{rm},q^{em}$ | Sender Transition<br/>$(s_n \xrightarrow{} s_{n+1})$<br/>$q^{cs},q^{rm},q^{em}$ | Message Type<br/>$\rightharpoonup$<br/>$M_{ij}$ |
|:------------------------------------------------------------------:|:-------------------------------------------------------------------------------:|:-----------------------------------------------:|
|                     $vfd \cdot\cdot\cdot,S,*$                      |       $\xrightarrow{\mathbf{V}} Vfd \cdot\cdot\cdot, \xrightarrow{r} R,-$       |                      $CV$                       |
|                  $Vfd \cdot\cdot\cdot,\lnot C,*$                   |               $\xrightarrow{\mathbf{F}} VFd \cdot\cdot\cdot, -,-$               |                      $CF$                       |
|                  $VFd \cdot\cdot\cdot,\lnot C,*$                   |               $\xrightarrow{\mathbf{D}} VFD \cdot\cdot\cdot, -,-$               |                      $CD$                       |
|           $\cdot\cdot\cdot p \cdot\cdot,\lnot C,\{N,X\}$           |          $\xrightarrow{\mathbf{P}} \cdot\cdot\cdot P \cdot\cdot, -,-$           |                      $CP$                       |
|              $\cdot\cdot\cdot p \cdot\cdot,\lnot C,P$              |  $\xrightarrow{\mathbf{P}} \cdot\cdot\cdot P \cdot\cdot, -,\xrightarrow{r} N$   |                      $CP$                       |
|           $\cdot\cdot\cdot p \cdot\cdot,\lnot C,\{A,R\}$           |  $\xrightarrow{\mathbf{P}} \cdot\cdot\cdot P \cdot\cdot, -,\xrightarrow{t} X$   |                      $CP$                       |
|             $\cdot\cdot\cdot px \cdot,\lnot C,\{N,X\}$             |           $\xrightarrow{\mathbf{X+P}} \cdot\cdot\cdot PX \cdot, -,-$            |                     $CX+CP$                     |
|                $\cdot\cdot\cdot px \cdot,\lnot C,P$                |   $\xrightarrow{\mathbf{X+P}} \cdot\cdot\cdot PX \cdot, -,\xrightarrow{r} N$    |                     $CX+CP$                     |
|             $\cdot\cdot\cdot px \cdot,\lnot C,\{A,R\}$             |   $\xrightarrow{\mathbf{X+P}} \cdot\cdot\cdot PX \cdot, -,\xrightarrow{t} X$    |                     $CX+CP$                     |
|             $\cdot\cdot\cdot Px \cdot,\lnot C,\{N,X\}$             |            $\xrightarrow{\mathbf{X}} \cdot\cdot\cdot PX \cdot, -,-$             |                      $CX$                       |
|                $\cdot\cdot\cdot Px \cdot,\lnot C,P$                |    $\xrightarrow{\mathbf{X}} \cdot\cdot\cdot PX \cdot, -,\xrightarrow{r} N$     |                      $CX$                       |
|             $\cdot\cdot\cdot Px \cdot,\lnot C,\{A,R\}$             |    $\xrightarrow{\mathbf{X}} \cdot\cdot\cdot PX \cdot, -,\xrightarrow{t} X$     |                      $CX$                       |
|           $\cdot\cdot\cdot\cdot\cdot a,\lnot C,\{N,X\}$            |           $\xrightarrow{\mathbf{A}} \cdot\cdot\cdot\cdot\cdot A, -,-$           |                      $CA$                       |
|              $\cdot\cdot\cdot\cdot\cdot a,\lnot C,P$               |   $\xrightarrow{\mathbf{A}} \cdot\cdot\cdot\cdot\cdot A, -,\xrightarrow{r} N$   |                      $CA$                       |
|           $\cdot\cdot\cdot\cdot\cdot a,\lnot C,\{A,R\}$            |   $\xrightarrow{\mathbf{A}} \cdot\cdot\cdot\cdot\cdot A, -,\xrightarrow{t} X$   |                      $CA$                       |


!!! note inline end "CS Messages Received and State Transitions"

    $$S_i \times M_{ji}^{cs} \rightarrow S_i$$


### CS Messages Received and State Transitions

The following table lists the effects of receiving a
CS message to the receiving Participant's state coupled with the expected response message.


| Received Msg.<br/>$\leftharpoondown$<br/>$M_{ji}$ | Receiver Precondition<br/>$s_n \in S_i$<br/>$q^{cs},q^{rm},q^{em}$ | Receiver Transition<br/>$(s_n \xrightarrow{} s_{n+1})$<br/>$q^{cs},q^{rm},q^{em}$ | Response Msg.<br/>$\rightharpoonup$<br/>$M_{ij}$ |
|:-------------------------------------------------:|:------------------------------------------------------------------:|:---------------------------------------------------------------------------------:|:------------------------------------------------:|
|                       $CV$                        |                           $*,\lnot C,*$                            |                                      $-,-,-$                                      |                       $CK$                       |
|                       $CF$                        |                           $*,\lnot C,*$                            |                                      $-,-,-$                                      |                       $CK$                       |
|                       $CD$                        |                           $*,\lnot C,*$                            |                                      $-,-,-$                                      |                       $CK$                       |
|                       $CP$                        |              $\cdot\cdot\cdot p \cdot\cdot,\lnot C,P$              |    $\xrightarrow{\mathbf{P}} \cdot\cdot\cdot P \cdot\cdot,-,\xrightarrow{r} N$    |                       $CK$                       |
|                       $CP$                        |           $\cdot\cdot\cdot p \cdot\cdot,\lnot C,\{A,R\}$           |    $\xrightarrow{\mathbf{P}} \cdot\cdot\cdot P \cdot\cdot,-,\xrightarrow{t} X$    |                       $CK$                       |
|                       $CP$                        |           $\cdot\cdot\cdot p \cdot\cdot,\lnot C,\{N,X\}$           |            $\xrightarrow{\mathbf{P}} \cdot\cdot\cdot P \cdot\cdot,-,-$            |                       $CK$                       |
|                       $CP$                        |              $\cdot\cdot\cdot P \cdot\cdot,\lnot C,*$              |                                      $-,-,-$                                      |                       $CK$                       |
|                       $CX$                        |                $\cdot\cdot\cdot px \cdot,\lnot C,P$                |     $\xrightarrow{\mathbf{X+P}} \cdot\cdot\cdot PX \cdot,-,\xrightarrow{r} N$     |                       $CK$                       |
|                       $CX$                        |             $\cdot\cdot\cdot px \cdot,\lnot C,\{A,R\}$             |     $\xrightarrow{\mathbf{X+P}} \cdot\cdot\cdot PX \cdot,-,\xrightarrow{t} X$     |                       $CK$                       |
|                       $CX$                        |             $\cdot\cdot\cdot px \cdot,\lnot C,\{N,X\}$             |             $\xrightarrow{\mathbf{X+P}} \cdot\cdot\cdot PX \cdot,-,-$             |                       $CK$                       |
|                       $CX$                        |                $\cdot\cdot\cdot Px \cdot,\lnot C,*$                |              $\xrightarrow{\mathbf{X}} \cdot\cdot\cdot PX \cdot,-,-$              |                       $CK$                       |
|                       $CX$                        |                $\cdot\cdot\cdot PX \cdot,\lnot C,*$                |                                      $-,-,-$                                      |                       $CK$                       |
|                       $CA$                        |               $\cdot\cdot\cdot p \cdot a,\lnot C,P$                |     $\xrightarrow{\mathbf{A}} \cdot\cdot\cdot P \cdot A,-,\xrightarrow{r} N$      |                       $CK$                       |
|                       $CA$                        |            $\cdot\cdot\cdot p \cdot a,\lnot C,\{A,R\}$             |                  $\xrightarrow{\mathbf{A}} \cdot\cdot\cdot P \cdot A,-,\xrightarrow{t} X$                   |                       $CK$                       |
|                       $CA$                        |            $\cdot\cdot\cdot p \cdot a,\lnot C,\{N,X\}$             |                          $\xrightarrow{\mathbf{A}} \cdot\cdot\cdot P \cdot A,-,-$                           |                       $CK$                       |
|                       $CA$                        |               $\cdot\cdot\cdot P \cdot a,\lnot C,*$                |                          $\xrightarrow{\mathbf{A}} \cdot\cdot\cdot P \cdot A,-,-$                           |                       $CK$                       |
|                       $CA$                        |              $\cdot\cdot\cdot\cdot\cdot A,\lnot C,*$               |                                      $-,-,-$                                      |                       $CK$                       |
| $CE$ | $*,\lnot C,*$ | $-,-,-$ |                     $CK+GI$                      |
| $CK$ | $*,\lnot C,*$ | $-,-,-$ |                       $-$                        |


## General Transition Functions

Finally, for the sake of completeness, we show that general inquiries, acknowledgments, and errors are otherwise independent 
of the rest of the processes. 
No state changes are expected to occur based on the receipt of a General message.

!!! tip "General Messages are not a *No-Op*"

    Note that we do not mean to imply that the *content* of such a message is expected to have no effect on the progression 
    of a case, merely that the act of sending or receiving a general message itself does not imply any necessary state 
    change to either the sender or receiver Participants.

!!! note inline end "General Messages Sent and State Transitions"
    
    $$S_i \times M_{ij}^{gen} \rightarrow S_i$$

### General Messages Sent and State Transitions

The following table lists each general message and the states in which it is appropriate to send along with the
corresponding sender state. 



| Sender Precondition<br/>$(s_n \in S_i)$<br/>$q^{cs},q^{rm},q^{em}$ | Sender Transition<br/>$(s_n \xrightarrow{} s_{n+1})$<br/>$q^{cs},q^{rm},q^{em}$ | Message Type<br/>$\rightharpoonup$<br/>$M_{ij}$ |
|:------------------------------------------------------------------:|:-------------------------------------------------------------------------------:|:-----------------------------------------------:|
|                              $*,*,*$                               |                                     $-,-,-$                                     |                      $GI$                       |
|                              $*,*,*$                               |                                     $-,-,-$                                     |                      $GK$                       |
|                              $*,*,*$                               |                                     $-,-,-$                                     |                      $GE$                       |

!!! note inline end "General Messages Received and State Transitions"

    $$S_i \times M_{ji}^{gen} \rightarrow S_i$$

### General Messages Received and State Transitions

The next table lists the effects of receiving a general message to the receiving Participant's state coupled with the 
expected response message.



| Received Msg.<br/>$\leftharpoondown$<br/>$M_{ji}$ | Receiver Precondition<br/>$s_n \in S_i$<br/>$q^{cs},q^{rm},q^{em}$ | Receiver Transition<br/>$(s_n \xrightarrow{} s_{n+1})$<br/>$q^{cs},q^{rm},q^{em}$ | Response Msg.<br/>$\rightharpoonup$<br/>$M_{ij}$ |
|:-------------------------------------------------:|:------------------------------------------------------------------:|:---------------------------------------------------------------------------------:|:------------------------------------------------:|
|                      $GI$                        |                           $*,*,*$                            |                                      $-,-,-$                                      |                       $GK$                       |
|                      $GK$                        |                           $*,*,*$                            |                                      $-,-,-$                                      |                       $-$                        |
|                      $GE$                        |                           $*,*,*$                            |                                      $-,-,-$                                      |                       $GI$                       |