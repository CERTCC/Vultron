# Process CS Messages Behavior {#sec:process_cs_messages_bt}

The Process CS Messages Behavior Tree is shown below.

```mermaid
---
title: Process CS Messages Behavior Tree
---
flowchart LR
    seq["&rarr;"]
    is_C_msg(["is C* msg?"])
    seq --> is_C_msg
    fb["?"]
    seq --> fb
    is_CK_msg(["is CK msg?"])
    fb --> is_CK_msg
    seq2["&rarr;"]
    fb --> seq2
    fb2["?"]
    seq2 --> fb2
    cs_global["Handle CS<br/>Participant-agnostic<br/>status msg"]
    fb2 --> cs_global
    cs_pspec["Handle CS<br/>Participant-specific<br/>status msg"]
    fb2 --> cs_pspec
    err_seq["&rarr;"]
    fb2 --> err_seq
    is_ce_msg(["is CE msg?"])
    err_seq --> is_ce_msg
    emit_gi["emit GI"]
    err_seq --> emit_gi
    emit_ck["emit CK"]
    seq2 --> emit_ck
    emit_ce["emit CE"]
    fb --> emit_ce
```

We are still working through the children of [Receive Messages](/topics/behavior_logic/msg_intro_bt/) behavior tree.
And as we've come to expect, a precondition check leads to a fallback node in which CS acknowledgement
messages (_CK_) receive no further attention and return *Success*.

The main CS message-handling sequence comes next, with all matching incoming messages resulting in emission of an 
acknowledgment message (_CK_).
These messages are presented as sub-trees below:

- [Participant-agnostic CS Status Messages](#participant-agnostic-cs-status-messages)
- [Participant-Specific CS Status Messages](#participant-specific-cs-status-messages)

Returning from handling regular CS messages, the tree next handles error messages (_CE_) with the familiar motif
of an error (_CE_) triggering a general inquiry (_GI_) to seek resolution.

Finally, the tree has handled all expected messages, so anything else would result in an error
condition and emission of a _CE_ message accordingly.


## Participant-agnostic CS Status Messages

The tree first handles messages indicating a Participant-agnostic CS change.

```mermaid
---
title: Process CS Participant-agnostic Status Messages Behavior Tree
---
flowchart LR
    global_seq["&rarr;"]
    global_fb["?"]
    global_seq --> global_fb
    cp_seq["&rarr;"]
    global_fb --> cp_seq
    is_CP_msg(["is CP msg?"])
    cp_seq --> is_CP_msg
    cp_fb["?"]
    cp_seq --> cp_fb
    cp_cs_not_P(["CS not in ...P..?"])
    cp_fb --> cp_cs_not_P
    cp_cs_to_P["CS &rarr; ...P.."]
    cp_fb --> cp_cs_to_P
    cx_seq["&rarr;"]
    global_fb --> cx_seq
    is_CX_msg(["is CX msg?"])
    cx_seq --> is_CX_msg
    cx_fb["?"]
    cx_seq --> cx_fb
    cx_cs_not_PXA(["CS not in ...PX.?"])
    cx_fb --> cx_cs_not_PXA
    cx_seq2["&rarr;"]
    cx_fb --> cx_seq2
    cx_x_fb["?"]
    cx_seq2 --> cx_x_fb
    cs_in_x(["CS in ...X..?"])
    cx_x_fb --> cs_in_x
    cx_to_x["CS &rarr; ....X."]
    cx_x_fb --> cx_to_x
    cx_p_fb["?"]
    cx_seq2 --> cx_p_fb
    cs_in_p(["CS in ...PX.?"])
    cx_p_fb --> cs_in_p
    cx_to_p["CS &rarr; ...PX.<br/>(emit CP)"]
    cx_p_fb --> cx_to_p
    ca_seq["&rarr;"]
    global_fb --> ca_seq
    is_CA_msg(["is CA msg?"])
    ca_seq --> is_CA_msg
    ca_fb["?"]
    ca_seq --> ca_fb
    ca_cs_not_a(["CS not in .....A?"])
    ca_fb --> ca_cs_not_a
    ca_cs_to_a["CS &rarr; .....A"]
    ca_fb --> ca_cs_to_a
    terminate["terminate embargo"]
    global_seq --> terminate
```


Information that the vulnerability has been made public (_CP_) is met
with a transition to the *Public Aware* state in the CS model when
necessary. Similarly, information that an exploit has been made public
forces both the __X__ and __P__ transitions, as necessary.
Because the __P__ transition, should it occur in response to a
_CX_ message, represents possibly new information to the case, it
triggers the emission of a _CP_ message to convey this information to
the other Participants. Likewise, a message indicating attacks underway
triggers the __A__ transition.

Again, we note that any of the __P__, __X__, or
__A__ transitions in the CS model imply that no new embargo should be
entered, and any existing embargo should be terminated. Hence, the
sequence described in the previous paragraph leads to the [embargo
termination tree](/topics/behavior_logic/em_terminate_bt/).

## Participant-Specific CS Status Messages

Next, we see that messages indicating *Vendor Awareness* (_CV_), *Fix
Readiness* (_CF_), and *Fix Deployed* (_CD_) are treated as mere status
updates for the Participant because they are participant-specific.
They are recognized and acknowledged but trigger no further action directly. 

```mermaid
---
title: Process CS Participant-Specific Messages Behavior Tree
---
flowchart LR
    seq["&rarr;"]
    is_C_msg(["is CV, CF, or CD msg?"])
    seq --> is_C_msg
    update_status["update sender status"]
    seq --> update_status
```


Recall from
[Model Interactions](/topics/process_models/model_interactions/) and
the [Formal Protocol](/reference/formal_protocol/) that the 
$vfd\cdot\cdot\cdot \rightarrow \dots \rightarrow VFD\cdot\cdot\cdot$ portion of the
CS model is unique to each Vendor Participant, and similarly that the
$\cdot\cdot d \cdot\cdot\cdot \rightarrow \cdot\cdot D \cdot\cdot\cdot$ portion is unique to
each Participant in the Deployer role.
Therefore, messages representing another Participant's status change for this portion of the
CS do not directly affect the receiving Participant's status.
This is not to say that the Participant might not choose to take some action based on their knowledge of a
Vendor's (or Deployer's) status. 
Rather, such follow-up would be expected to occur as part of the Participant's [*do work* process](/topics/behavior_logic/do_work_bt/).


