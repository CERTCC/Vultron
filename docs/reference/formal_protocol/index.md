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


## Formal MPCVD Protocol Redux {#sec:formal_protocol_redux}

{== TODO integrate this section ==}

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


