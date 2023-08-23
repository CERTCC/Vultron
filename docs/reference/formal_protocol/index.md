# A Formal Protocol Definition for MPCVD {#sec:formal_protocol}

The MPCVD process can be described as a Communicating Hierarchical State Machine.
In this section, we begin by laying out the requirements for a formal protocol
definition followed by a step-by-step walkthrough of each of those requirements
as they relate to the [RM](../../topics/process_models/rm/index.md), [EM](../../topics/process_models/em/index.md), and [CS](../../topics/process_models/cs/index.md)
models described elsewhere.

## Communication Protocol Definitions {#sec:protocol_definition}

A communication protocol allows independent processes, represented as finite state machines, to coordinate their state 
transitions through the passing of messages. [Brand and Zafiropulo](https://doi.org/10.1145/322374.322380) defined
a protocol as follows. 

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

We detail each of these below or in subsequent pages:

- $N$ [below](#number-of-processes)
- ${ \langle S_i \rangle}^N_{i=1}$, and ${ \langle o_i \rangle }^N_{i=1}$ in [States](states.md),
- ${ \langle M_{i,j} \rangle }^N_{i,j=1}$ in [Message Types](messages.md),
- ${ succ }$ in [Transition Functions](transitions.md)

## Number of Processes

The processes we are concerned with represent the different Participants
in their roles (Finder, Vendor, Coordinator, Deployer, and Other). Each
Participant has their own process, but Participants might take on
multiple roles in a given case.

!!! note "_Number of Processes_"

    The total number of processes $N$ is simply the count of unique Participants.

    $$N = |Participants| = | Reporters \cup Vendors \cup Coordinators \cup Deployers \cup Others |$$


