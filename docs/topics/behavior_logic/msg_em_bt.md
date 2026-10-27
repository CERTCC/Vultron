---
stakeholder_type: [project-contributor]
---

# Process EM Messages Behavior

## Requirements

{% include-markdown "./_requirements_pointer.md" %}

{% include-markdown "./_em_message_requirements.md" %}

{% include-markdown "./_conformant_implementation_note.md" %}

{% include-markdown "./_legacy_diagram_note.md" %}

The figure below shows the Process EM Messages Behavior Tree.

```mermaid
---
title: Process EM Messages Behavior Tree
---
flowchart LR
    seq["&rarr;"]
    is_E_msg(["is E* msg?"])
    seq --> is_E_msg
    fb["?"]
    seq --> fb
    is_EK_msg(["is EK msg?"])
    fb --> is_EK_msg
    seq2["&rarr;"]
    fb --> seq2
    fb2["?"]
    seq2 --> fb2
    ee_seq["&rarr;"]
    fb2 -->|A| ee_seq
    is_EE_msg(["is EE msg?"])
    ee_seq --> is_EE_msg
    ee_emit_GI["emit GI"]
    ee_seq --> ee_emit_GI
    et_seq["&rarr;"]
    fb2 -->|B| et_seq
    is_ET_msg(["is ET msg?"])
    et_seq --> is_ET_msg
    et_fb["?"]
    et_seq --> et_fb
    em_x(["EM in X?"])
    et_fb --> em_x
    et_seq2["&rarr;"]
    et_fb --> et_seq2
    em_a_r(["EM in A or R?"])
    et_seq2 --> em_a_r
    et_em_to_X["EM &rarr; X"]
    et_seq2 --> et_em_to_X
    er_seq["&rarr;"]
    fb2 -->|C| er_seq
    is_ER_msg(["is ER msg?"])
    er_seq --> is_ER_msg
    er_fb["?"]
    er_seq --> er_fb
    em_none(["EM in N?"])
    er_fb --> em_none
    er_seq2["&rarr;"]
    er_fb --> er_seq2
    em_p(["EM in P?"])
    er_seq2 --> em_p
    er_em_to_n["EM &rarr; N"]
    er_seq2 --> er_em_to_n
    viable_seq["&rarr;"]
    fb2 -->|D| viable_seq
    cs_in_pxa(["CS in ...pxa?"])
    viable_seq -->|D1| cs_in_pxa
    handle_viab["handle viable embargo"]
    viable_seq -->|D2| handle_viab
    non_viable_seq["&rarr;"]
    fb2 -->|E| non_viable_seq
    cs_not_in_pxa(["CS not in ...pxa?"])
    non_viable_seq --> cs_not_in_pxa
    terminate["terminate embargo"]
    non_viable_seq --> terminate
    emit_ek["emit EK"]
    seq2 --> emit_ek
    emit_ee["emit EE"]
    fb --> emit_ee
```

This tree is a child of the fallback node that starts in [Receiving Messages Behavior](msg_intro_bt.md).
The tree starts with a precondition check for EM message types and then goes to a fallback node.
EM acknowledgment messages (*EK*) get no more processing and return *Success*.

## Messages That Lead to a Simple Acknowledgment

Next comes a branch that handles all the messages that get a simple acknowledgment (*EK*).

(A) The first case is embargo error messages (*EE*).
An *EE* message also triggers a general inquiry (*GI*) message, to try to solve the problem.

(B) The second case is embargo termination messages (*ET*).
If the Participant is already in the EM *eXited* state (*X*), the tree does nothing more (other than the *EK*).
Otherwise, if the Participant is in the *Active* or *Revise* EM state, the *ET* message triggers a state transition $q^{em} \xrightarrow{t} X$.

(C) The third case is embargo rejections.
A simple sequence handles them and returns the state from *Proposed* to *None*.

### Handling Viable Embargo Messages

(D) The last part of the simple acknowledgment branch handles EM messages that arrive when the case state lets an embargo be viable ($q^{cs} \in \cdot\cdot\cdot pxa$).
The tree can do different actions in this case state, as the next diagram shows.

```mermaid
---
title: Handling Viable Embargo Messages
---
flowchart LR
    fb["?"]
    ep_seq["&rarr;"]
    fb -->|D2a| ep_seq
    is_EP_msg(["is EP msg?"])
    ep_seq --> is_EP_msg
    ep_fb["?"]
    ep_seq --> ep_fb
    ep_em_p(["EM in P?"])
    ep_fb --> ep_em_p
    ep_seq2["&rarr;"]
    ep_fb --> ep_seq2
    em_none(["EM in N?"])
    ep_seq2 --> em_none
    ep_em_to_p["EM &rarr; P"]
    ep_seq2 --> ep_em_to_p
    ea_seq["&rarr;"]
    fb -->|D2b| ea_seq
    is_EA_msg(["is EA msg?"])
    ea_seq --> is_EA_msg
    ea_fb["?"]
    ea_seq --> ea_fb
    em_a(["EM in A?"])
    ea_fb --> em_a
    ea_seq2["&rarr;"]
    ea_fb --> ea_seq2
    ea_em_p(["EM in P?"])
    ea_seq2 --> ea_em_p
    ea_em_to_a["EM &rarr; A"]
    ea_seq2 --> ea_em_to_a
    ev_seq["&rarr;"]
    fb -->|D2c| ev_seq
    is_EV_msg(["is EV msg?"])
    ev_seq --> is_EV_msg
    ev_fb["?"]
    ev_seq --> ev_fb
    ev_em_r(["EM in R?"])
    ev_fb --> ev_em_r
    ev_seq2["&rarr;"]
    ev_fb --> ev_seq2
    ev_em_a(["EM in A?"])
    ev_seq2 --> ev_em_a
    ev_em_to_r["EM &rarr; R"]
    ev_seq2 --> ev_em_to_r
    ej_ec_seq["&rarr;"]
    fb -->|D2d| ej_ec_seq
    is_EJ_msg(["is EJ or EC msg?"])
    ej_ec_seq --> is_EJ_msg
    ej_ec_fb["?"]
    ej_ec_seq --> ej_ec_fb
    ej_ec_em_A(["EM in A?"])
    ej_ec_fb --> ej_ec_em_A
    ej_ec_seq2["&rarr;"]
    ej_ec_fb --> ej_ec_seq2
    ej_ec_em_r(["EM in R?"])
    ej_ec_seq2 --> ej_ec_em_r
    ej_ec_fb2["?"]
    ej_ec_seq2 --> ej_ec_fb2
    ej_seq["&rarr;"]
    ej_ec_fb2 --> ej_seq
    ej_is_EJ_msg(["is EJ msg?"])
    ej_seq --> ej_is_EJ_msg
    ej_em_to_A["EM &rarr; A"]
    ej_seq --> ej_em_to_A
    ec_seq["&rarr;"]
    ej_ec_fb2 --> ec_seq
    ec_is_EC_msg(["is EC msg?"])
    ec_seq --> ec_is_EC_msg
    ec_em_to_A["EM &rarr; A"]
    ec_seq --> ec_em_to_A
```

(D2a) An embargo proposal (*EP*) moves the state from *None* to *Proposed*.
If the state is already *Proposed*, it stays in *Proposed*.

(D2b) An embargo acceptance (*EA*) moves the state from *Proposed* to *Active*.

(D2c) An embargo revision proposal (*EV*) works like the *EP* behavior.
It moves the state from *Active* to *Revise*, or the state stays in *Revise*, as applicable.

(D2d) Last, the tree handles a revision rejection (*EJ*) or acceptance (*EC*) in the *Revise* state.

Back up the tree, *Success* in any of the branches in this paragraph or the previous paragraph causes an acknowledgment message *EK*.

## Messages That Require More than a Simple Acknowledgment

(E) Now go back to the tree at the top of the page.
The next branch handles EM messages when an embargo is no longer viable.
That is, attacks are occurring, or the exploit or the vulnerability is public ($q^{cs} \not \in \cdot\cdot\cdot pxa$).
This branch goes to the [Terminate Embargo tree](em_terminate_bt.md), which can emit other messages.

Last, go back to the end of the tree at the top of the page.
If no other branch succeeds, the tree emits an embargo error (*EE*) message to report the failure.
