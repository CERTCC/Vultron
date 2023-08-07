# Process RM Messages Behavior {#sec:process_rm_messages_bt}

The Process RM Messages Behavior Tree is shown below.

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
    fb2 --> rs_seq
    is_RS_msg(["is RS msg?"])
    rs_seq --> is_RS_msg
    rs_fb["?"]
    rs_seq --> rs_fb
    rm_not_S(["RM not in S?"])
    rs_fb --> rm_not_S
    rm_to_R(["RM &rarr; R"])
    rs_fb --> rm_to_R
    rs_fb2["?"]
    rs_seq --> rs_fb2
    role_not_vendor(["role != vendor?"])
    rs_fb2 --> role_not_vendor
    cs_in_V(["CS in V.....?"])
    rs_fb2 --> cs_in_V
    cs_to_V(["CS &rarr; Vfd...<br/>(emit CV)"])
    rs_fb2 --> cs_to_V
    re_seq["&rarr;"]
    fb2 --> re_seq
    is_RE_msg(["is RE msg?"])
    re_seq --> is_RE_msg
    emit_GI(["emit GI"])
    re_seq --> emit_GI
    other_seq["&rarr;"]
    fb2 --> other_seq
    o_rm_not_S(["RM not in S?"])
    other_seq --> o_rm_not_S
    update_sender_status["update sender status"]
    other_seq --> update_sender_status
    emit_RK(["emit RK"])
    seq2 --> emit_RK
    emit_RE(["emit RE"])
    fb --> emit_RE
```

This tree is a child of the fallback node started in [Receiving Messages Behavior](/topics/behavior_logic/msg_intro_bt/).
Beginning with a precondition check for any RM message type, the tree proceeds to a fallback node.
RM acknowledgment messages (_RK_) receive no further attention and return *Success*.

Next comes the main RM message processing sequence.
A fallback node covers three major cases:

-   First comes a sequence that handles new reports (_RS_ when
    $q^{rm} \in S$). This branch changes the recipient's
    RM state
    regardless of the Participant's role. If the Participant happens to
    be a Vendor and the Vendor was previously unaware of the
    vulnerability described by the report, the Vendor would also note
    the CS
    transition from $q^{cs} \in vfd \xrightarrow{\mathbf{V}} Vfd$ and
    emit a corresponding _CV_ message.

-   Next, we see that an RM Error (_RE_) results in the emission
    of a general inquiry (_GI_) for Participants to sort out what the
    problem is, along with an _RK_ to acknowledge receipt of the error.

-   Finally, recall that the RM process is unique to each
    CVD
    Participant, so most of the remaining RM messages are simply informational
    messages about other Participants' statuses that do not directly
    affect the receiver's status. Therefore, if there is already an
    associated case ($q^{rm} \not\in S$), the recipient might update
    their record of the sender's state, but no further action is needed.

For all three cases, an _RK_ message acknowledges receipt of the
message. Any unhandled message results in an _RE_ response, indicating
an error.

