# Terminate Embargo Behavior

The Terminate Embargo Behavior Tree is shown in the diagram below.
It consists of two major behaviors depending on whether an embargo has been established or not.

```mermaid
---
title: Terminate Embargo Behavior Tree
---
flowchart LR
    fb[?]
    em_n_or_x(["EM N or X?"])
    fb -->|A| em_n_or_x
    p_seq["&rarr;"]
    fb -->|B| p_seq
    em_p(["EM P?"])
    p_seq --> em_p
    p_fb[?]
    p_seq --> p_fb
    p_cs_not_pxa(["CS not in ...pxa?"])
    p_fb --> p_cs_not_pxa
    other(["other reason?"])
    p_fb --> other
    p_em_to_n["EM P &rarr; N<br/>(emit ER)"]
    p_seq --> p_em_to_n
    ar_seq["&rarr;"]
    fb -->|C| ar_seq
    em_a_or_r(["EM A or R?"])
    ar_seq --> em_a_or_r
    ar_fb[?]
    ar_seq --> ar_fb
    ar_cs_not_pxa(["CS not in ...pxa?"])
    ar_fb --> ar_cs_not_pxa
    ar_timer_expired(["timer expired?"])
    ar_fb --> ar_timer_expired
    ar_other(["other reason?"])
    ar_fb --> ar_other
    ar_exit_embargo["exit embargo"]
    ar_seq --> ar_exit_embargo
    ar_em_to_x["EM &rarr; X<br/>(emit ET)"]
    ar_seq --> ar_em_to_x
```

(A) If the EM state is *None* or *eXited*, ($q^{em} \in \{N{,}X\}$), the tree succeeds immediately.

(B) The next node handles the scenario where no embargo has been established.
The behavior descends into a sequence that checks whether we are in $Proposed$ ($q^{em} \in P$).
If we are, we check to see if there is a reason to exit the embargo negotiation process.
One such reason is that the case state is outside the embargo "habitable zone," but there may be others that we leave
unspecified.
If any reason is found, then the proposal is rejected, the state returns to *None*, and an $ER$ message is sent.

(C) Should that branch fail, we still need to handle the situation where an embargo has already been established.
Following a confirmation that we are in either *Active* or *Revise*, we again look for reasons to exit, this time
adding the possibility of timer expiration to the conditions explicitly called out.
Terminating an existing embargo might have some other teardown procedures to be completed, which we represent as the
*exit embargo* task.
Finally, the EM state is updated to *eXited* and an $ET$ message is emitted.

!!! tip inline end "See also"

    - [Early Termination](../process_models/em/early_termination.md)
    - [Threat Monitoring Behavior](monitor_threats_bt.md)
    - [Message Handling Behavior](msg_intro_bt.md)

The Terminate Embargo Behavior Tree appears in multiple locations in the
larger tree.
We will encounter it again as a possible response to evidence collected via
[threat monitoring](monitor_threats_bt.md)
as well as in response to certain [CS or EM messages](msg_intro_bt.md)
in states when an embargo is no longer viable.
