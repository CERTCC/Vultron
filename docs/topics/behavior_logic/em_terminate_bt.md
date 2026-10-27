---
stakeholder_type: [project-contributor]
---

# Terminate Embargo Behavior

## Requirements

{% include-markdown "./_requirements_pointer.md" %}

- [EMB-13](../../reference/specs/protocol.md#emb-13) — Enter EM Exited
- [EMB-14](../../reference/specs/protocol.md#emb-14) — Actor-Voluntary Embargo Termination (Trigger Side)
- [EMB-19](../../reference/specs/protocol.md#emb-19) — Embargo Teardown Announcement

{% include-markdown "./_conformant_implementation_note.md" %}

{% include-markdown "./_legacy_diagram_note.md" %}

The diagram below shows the Terminate Embargo Behavior Tree.
It has two major behaviors.
Which behavior applies depends on whether an embargo is established.

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

(A) If the EM state is *None* or *eXited* ($q^{em} \in \{N{,}X\}$), the tree succeeds immediately.

(B) The next node handles the situation where no embargo is established.
The behavior goes into a sequence that checks whether the EM state is $Proposed$ ($q^{em} \in P$).
If it is, the sequence checks whether there is a reason to exit the embargo negotiation process.

One such reason is that the case state is outside the embargo "habitable zone".
Other reasons can exist, but we do not specify them.
If the sequence finds a reason, the tree rejects the proposal, the state returns to *None*, and the tree sends an $ER$ message.

(C) If that branch fails, the tree must still handle the situation where an embargo is already established.
First, the tree confirms that the EM state is *Active* or *Revise*.
Then it looks for reasons to exit again.
This time, the explicit conditions also include timer expiration.

To terminate an existing embargo, the Participant can have other teardown procedures to complete.
The *exit embargo* task represents these procedures.
Last, the tree changes the EM state to *eXited* and emits an $ET$ message.

!!! tip inline end "See also"

    - [Early Termination](../process_models/em/early_termination.md)
    - [Threat Monitoring Behavior](monitor_threats_bt.md)
    - [Message Handling Behavior](msg_intro_bt.md)

The Terminate Embargo Behavior Tree occurs in multiple locations in the larger tree.
It is a possible response to evidence that [threat monitoring](monitor_threats_bt.md) collects.
It is also a response to some [CS or EM messages](msg_intro_bt.md) in states where an embargo is no longer viable.
