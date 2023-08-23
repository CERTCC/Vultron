# Process EM Messages Behavior {#sec:process_em_messages_bt}

The Process EM Messages Behavior Tree is shown below.

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
    fb2 --> ee_seq
    is_EE_msg(["is EE msg?"])
    ee_seq --> is_EE_msg
    ee_emit_GI["emit GI"]
    ee_seq --> ee_emit_GI
    et_seq["&rarr;"]
    fb2 --> et_seq
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
    fb2 --> er_seq
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
    fb2 --> viable_seq
    cs_in_pxa(["CS in ...pxa?"])
    viable_seq --> cs_in_pxa
    handle_viab["handle viable embargo"]
    viable_seq --> handle_viab
    non_viable_seq["&rarr;"]
    fb2 --> non_viable_seq
    cs_not_in_pxa(["CS not in ...pxa?"])
    non_viable_seq --> cs_not_in_pxa
    terminate["terminate embargo"]
    non_viable_seq --> terminate
    emit_ek["emit EK"]
    seq2 --> emit_ek
    emit_ee["emit EE"]
    fb --> emit_ee
```


It is a child of the fallback node started in [Receiving Messages Behavior]((./msg_intro_bt.md).
A precondition check for EM message types is followed by a fallback node. 
EM acknowledgment messages (_EK_) receive no further attention and return *Success*.

## Messages That Lead to a Simple Acknowledgment.

Next is a branch handling all the messages that will result in a simple acknowledgment (_EK_). 
First, we handle embargo error messages (_EE_), which additionally trigger a general inquiry (_GI_) message to attempt
to resolve the problem. 
Second are embargo termination messages (_ET_).
If the Participant is already in the EM *eXited* state (_X_), no further action is taken (aside from the _EK_).
Otherwise, if the Participant is in either *Active* or *Revise* EM states, the _ET_ message triggers a state
transition $q^{em} \xrightarrow{t} X$.
Embargo rejections are handled next in a simple sequence that returns the state from *Proposed* to *None*.

### Handling Viable Embargo Messages

The final chunk of the simple acknowledge branch handles EM messages received when the case state permits embargo viability
($q^{cs} \in \cdot\cdot\cdot pxa$).
A variety of actions can be taken in this case state, as shown in the next diagram.

```mermaid
---
title: Handling Viable Embargo Messages
---
flowchart LR
    fb["?"]
    ep_seq["&rarr;"]
    fb --> ep_seq
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
    fb --> ea_seq
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
    fb --> ev_seq
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
    fb --> ej_ec_seq
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

An embargo proposal (_EP_)
results in either a move from *None* to *Proposed* or stays in
*Proposed*, if that was already the case. An embargo acceptance (_EA_)
transitions from *Proposed* to *Active*. Similar to the _EP_ behavior,
an embargo revision proposal (_EV_) either moves from *Active* to
*Revise* or stays in *Revise*, as appropriate. Finally, we deal with
revision rejection (_EJ_) or acceptance (_EC_) when in the *Revise*
state. Climbing back up the tree, we see that *Success* in any of the
branches in this or the previous paragraph results in an acknowledgment
message _EK_.

## Messages That Require More than a Simple Acknowledgment.

Returning to the the tree at the top of the page, we come to a branch focused on
handling EM messages when an embargo is no longer viable---in other words, when the case has
reached a point where attacks are occurring, or either the exploit or the vulnerability has been made public
($q^{cs} \not \in \cdot\cdot\cdot pxa$).
This branch takes us to the [Terminate Embargo tree]((./em_terminate_bt.md), which may lead to
other messages being emitted.

Finally, back at the end of the tree at the top of the page, when no other branch has succeeded,
we emit an embargo error (_EE_) message to relay the failure.

