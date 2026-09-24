---
description: >
  The formal definition of the Vultron protocol as a Brand-Zafiropulo
  communication protocol, its global state, and its number of processes.
stakeholder_type: [platform-developer, process-researcher]
level: 400
---

# Protocol Definition

{% include-markdown "../../includes/normative.md" %}

This page defines the Multi-Party Coordinated Vulnerability Disclosure (MPCVD) protocol formally, as a communication protocol among independent processes.
It gives the protocol quadruple, the global state of a protocol, and the number of processes in a case.
The [States](states.md), [Messages](messages.md), and [Transitions](transitions.md) pages define the remaining elements of the quadruple.

## Communication protocol

A communication protocol allows independent processes, represented as finite state machines, to coordinate their state
transitions through the passing of messages. [Brand and Zafiropulo](https://doi.org/10.1145/322374.322380){:target="_blank"} defined
a protocol as follows.

!!! note "*Protocol* Formally Defined"

    A **protocol** with $N$ processes is a quadruple:

    $$
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

!!! note "*Global State* Formally Defined"

    The **global state** of a protocol given by the above is a pair $\langle S, C \rangle$, where

    -   $S$ is an $N$-tuple of states $\langle s_1,\dots,s_N \rangle$ with
    each $s_i$ representing the current state of process $i$.

    -   $C$ is an $N^2$-tuple
    $\langle c_{1,1},\dots, c_{1,N}, c_{2,1}, \dots \dots, c_{N,N} \rangle$,
    where each $c_{i,j}$ is a sequence of messages from $M_{i,j}$. The
    message sequence $c_{i,j}$ represents the contents of the channel
    from process $i$ to $j$. (Note that $c_{i,j}$ is empty when $i = j$
    since processes are presumed to not communicate with themselves.)

The elements of the quadruple are defined as follows:

| Element | Defined in |
|---|---|
| $N$ | [Number of processes](#number-of-processes), below |
| ${ \langle S_i \rangle}^N_{i=1}$ and ${ \langle o_i \rangle }^N_{i=1}$ | [States](states.md) |
| ${ \langle M_{i,j} \rangle }^N_{i,j=1}$ | [Messages](messages.md) |
| $succ$ | [Transitions](transitions.md) |

## Number of processes

The processes in an MPCVD case are its Participants.
Each Participant has one process, whatever roles it holds in the case.
The protocol's roles — Reporter, Vendor, Coordinator, Deployer, CVE Numbering Authority (CNA), and Observer — are defined in the [specification's role terminology](../vultron-spec/index.md#22-roles).
A Participant that holds several roles still counts once.

!!! note "*Number of Processes*"

    The total number of processes $N$ is the count of unique Participants.

    $$N = |Participants| = | Reporters \cup Vendors \cup Coordinators \cup Deployers \cup CNAs \cup Observers |$$
