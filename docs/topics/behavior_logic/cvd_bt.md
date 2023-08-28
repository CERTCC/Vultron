# CVD Behavior Tree

We begin at the root node of the CVD Behavior Tree shown in the figure below.
The root node is a simple loop that continues until an interrupt condition is met, representing the idea
that the CVD practice is meant to be continuous. In other words, we are intentionally not specifying the interrupt condition.

```mermaid
---
title: CVD Behavior Tree
---
flowchart LR
    root["#8634;"]
    seq["&rarr;"]
    discover_vulnerability["Discover Vulnerability"]
    receive_messages["Receive Messages"]
    report_management["Report Management"]
    embargo_management["Embargo Management"]
    root --> seq 
    seq -->|A| discover_vulnerability 
    seq -->|B| receive_messages
    seq -->|C| report_management
    seq -->|D| embargo_management
```

The main sequence is comprised of four main tasks:

-  (A) [*Discover Vulnerability.*](vuldisco_bt.md) Although not all Participants have the
    ability or motive to discover vulnerabilities, we include it as a
    task here to call out its importance to the overall
    CVD process. This task returns *Success* regardless of whether a vulnerability is found to allow execution to
    pass to the next task.

-  (B) [*Receive Messages*](msg_intro_bt.md). All coordination in CVD between Participants is done through
    the exchange of messages, regardless of how those messages are
    conveyed, stored, or presented. The receive messages task represents
    the Participant's response to receiving the various messages defined
    in the [formal protocol](../../reference/formal_protocol/index.md). Due to the degree of detail
    required to cover all the various message types, decomposition of
    this task node is deferred until [later](msg_intro_bt.md) so we can cover the next two items
    first. Before we proceed, it is sufficient to know that a new report arriving in the *receive messages* behavior 
    sets $q^{rm} \in S \xrightarrow{r} R$ and returns *Success*.

-  (C) [*Report Management*](rm_bt.md). This task embodies the [RM process](../process_models/rm/index.md)
    as integrated into the [formal protocol](../../reference/formal_protocol/index.md).

-  (D) [*Embargo Management*](em_bt.md). Similarly, this task represents the
    [EM process](../process_models/em/index.md) as integrated into the [formal protocol](../../reference/formal_protocol/index.md).

A further breakdown of a number of CVD tasks that fall outside the scope of the
[formal protocol](../../reference/formal_protocol/index.md) can be found in
[Do Work](do_work_bt.md).
In that section, we examine a number of behaviors that Participants may include as part of the work they do for reports 
in the _Accepted_ RM state ($q^{rm}\in A$).

Behaviors and state changes resulting from changes to the [CS model](../process_models/cs/index.md) are scattered throughout the other Behavior Trees
where relevant.

