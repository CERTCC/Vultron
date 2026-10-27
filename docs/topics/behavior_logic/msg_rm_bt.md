---
stakeholder_type: [project-contributor]
---

# Process RM Messages Behavior

## Requirements

{% include-markdown "./_requirements_pointer.md" %}

{% include-markdown "./_rm_message_requirements.md" %}

{% include-markdown "./_conformant_implementation_note.md" %}

{% include-markdown "./_legacy_diagram_note.md" %}

The figure below shows the Process RM Messages Behavior Tree.

```mermaid
---
title: Process RM Messages Behavior Tree
---
flowchart LR
    seq["&rarr;"]
    is_R_msg(["is R* msg?"])
    seq --> is_R_msg
    fb["?"]
    seq --> fb
    is_RK_msg(["is RK msg?"])
    fb --> is_RK_msg
    seq2["&rarr;"]
    fb --> seq2
    fb2["?"]
    seq2 --> fb2
    rs_seq["&rarr;"]
    fb2 -->|A| rs_seq
    is_RS_msg(["is RS msg?"])
    rs_seq --> is_RS_msg
    rs_fb["?"]
    rs_seq --> rs_fb
    rm_not_S(["RM not in S?"])
    rs_fb --> rm_not_S
    rm_to_R["RM &rarr; R"]
    rs_fb --> rm_to_R
    rs_fb2["?"]
    rs_seq --> rs_fb2
    role_not_vendor(["role != vendor?"])
    rs_fb2 --> role_not_vendor
    cs_in_V(["CS in V.....?"])
    rs_fb2 --> cs_in_V
    cs_to_V["CS &rarr; Vfd...<br/>(emit CV)"]
    rs_fb2 --> cs_to_V
    re_seq["&rarr;"]
    fb2 -->|B| re_seq
    is_RE_msg(["is RE msg?"])
    re_seq --> is_RE_msg
    emit_GI["emit GI"]
    re_seq --> emit_GI
    other_seq["&rarr;"]
    fb2 -->|C| other_seq
    o_rm_not_S(["RM not in S?"])
    other_seq --> o_rm_not_S
    update_sender_status["update sender status"]
    other_seq --> update_sender_status
    emit_RK["emit RK"]
    seq2 --> emit_RK
    emit_RE["emit RE"]
    fb --> emit_RE
```

This tree is a child of the fallback node that starts in [Receiving Messages Behavior](msg_intro_bt.md).
The tree starts with a precondition check for any RM message type and then goes to a fallback node.
RM acknowledgment messages (*RK*) get no more processing and return *Success*.

Next comes the main RM message processing sequence.
A fallback node covers three major cases:

- (A) The first case is a sequence that handles new reports (*RS* when $q^{rm} \in S$).
    This branch changes the RM state of the recipient, whatever the role of the Participant is.
    The Participant can be a Vendor that did not know about the vulnerability in the report before.
    In that case, the Vendor also records the CS transition $q^{cs} \in vfd \xrightarrow{\mathbf{V}} Vfd$ and emits a related *CV* message.

- (B) The second case is an RM Error (*RE*).
    The recipient emits a general inquiry (*GI*), so that the Participants can find the cause of the problem.
    The recipient also emits an *RK* to acknowledge receipt of the error.

- (C) The third case covers most of the remaining RM messages.
    Each CVD Participant has its own RM process.
    Thus, most of these messages give information about the status of other Participants and do not directly change the status of the receiver.
    If a case already exists ($q^{rm} \not\in S$), the recipient can update its record of the sender state.
    No other action is necessary.

For all three cases, an *RK* message acknowledges receipt of the message.
The tree replies with an *RE* message to any message that it does not handle, to show an error.
