## Receiving and Processing Messages Behavior {#sec:receive messages}

Now we return to the CVD Behavior Tree in Figure
[\[fig:bt_cvd_process\]](#fig:bt_cvd_process){reference-type="ref"
reference="fig:bt_cvd_process"} to pick up the last unexplored branch,
Receive Messages. The Receive Messages Behavior Tree is shown in Figure
[\[fig:bt_receive_messages\]](#fig:bt_receive_messages){reference-type="ref"
reference="fig:bt_receive_messages"}. It is a loop that continues until
all currently received messages have been processed. Each iteration
checks for unprocessed messages and handles them.

First, we encounter a case closure check. We assume that messages to
existing cases will have a case ID associated with all messages about
that case and that new report submissions will not have a case ID
assigned yet, implying they are in the RM *Start* state ($q^{rm} \in S$).
Therefore, new reports will pass this check every time. However,
messages received on an already *Closed* case will short-circuit here
and take no further action.

Assuming the message is regarding a new or unclosed case and the message
has not yet been processed, each message type is handled by a
process-specific Behavior Tree, which we discuss in the following
sections. Although each process-specific behavior is described in a
subsection and shown in its own figure, they are all part of the same
fallback node shown here.

### Process RM Messages Behavior {#sec:process_rm_messages_bt}

The Process RM
Messages Behavior Tree is shown in Figure
[\[fig:bt_process_rm_messages\]](#fig:bt_process_rm_messages){reference-type="ref"
reference="fig:bt_process_rm_messages"}. It is a child of the fallback
node started in Figure
[\[fig:bt_receive_messages\]](#fig:bt_receive_messages){reference-type="ref"
reference="fig:bt_receive_messages"}. Beginning with a precondition
check for any RM
message type, the tree proceeds to a fallback node.
RM acknowledgment
messages ($RK$) receive no further attention and return *Success*.

Next comes the main RM message processing sequence. A fallback
node covers three major cases:

-   First comes a sequence that handles new reports ($RS$ when
    $q^{rm} \in S$). This branch changes the recipient's
    RM state
    regardless of the Participant's role. If the Participant happens to
    be a Vendor and the Vendor was previously unaware of the
    vulnerability described by the report, the Vendor would also note
    the CS
    transition from $q^{cs} \in vfd \xrightarrow{\mathbf{V}} Vfd$ and
    emit a corresponding $CV$ message.

-   Next, we see that an RM Error ($RE$) results in the emission
    of a general inquiry ($GI$) for Participants to sort out what the
    problem is, along with an $RK$ to acknowledge receipt of the error.

-   Finally, recall that the RM process is unique to each
    CVD
    Participant, so most of the remaining RM messages are simply informational
    messages about other Participants' statuses that do not directly
    affect the receiver's status. Therefore, if there is already an
    associated case ($q^{rm} \not\in S$), the recipient might update
    their record of the sender's state, but no further action is needed.

For all three cases, an $RK$ message acknowledges receipt of the
message. Any unhandled message results in an $RE$ response, indicating
an error.

### Process EM Messages Behavior {#sec:process_em_messages_bt}

The Process EM
Messages Behavior Tree is shown in Figure
[\[fig:bt_process_em_messages\]](#fig:bt_process_em_messages){reference-type="ref"
reference="fig:bt_process_em_messages"}. As above, it is a child of the
fallback node started in Figure
[\[fig:bt_receive_messages\]](#fig:bt_receive_messages){reference-type="ref"
reference="fig:bt_receive_messages"}. A precondition check for
EM message types is
followed by a fallback node. EM acknowledgment messages ($EK$) receive no
further attention and return *Success*.

##### Messages That Lead to a Simple Acknowledgment.

Next is a branch handling all the messages that will result in a simple
acknowledgment ($EK$). First, we handle embargo error messages ($EE$),
which additionally trigger a general inquiry ($GI$) message to attempt
to resolve the problem. Second are embargo termination messages ($ET$).
If the Participant is already in the EM *eXited* state ($X$), no further action
is taken (aside from the $EK$). Otherwise, if the Participant is in
either *Active* or *Revise* EM states, the $ET$ message triggers a state
transition $q^{em} \xrightarrow{t} X$. Embargo rejections are handled
next in a simple sequence that returns the state from *Proposed* to
*None*.

The final chunk of the simple acknowledge branch handles
EM messages received
when the case state permits embargo viability
($q^{cs} \in \wc\wc\wc pxa$). A variety of actions can be taken in this
case state, as shown in the lower ($\diamondsuit$) tier of Figure
[\[fig:bt_process_em_messages\]](#fig:bt_process_em_messages){reference-type="ref"
reference="fig:bt_process_em_messages"}. An embargo proposal ($EP$)
results in either a move from *None* to *Proposed* or stays in
*Proposed*, if that was already the case. An embargo acceptance ($EA$)
transitions from *Proposed* to *Active*. Similar to the $EP$ behavior,
an embargo revision proposal ($EV$) either moves from *Active* to
*Revise* or stays in *Revise*, as appropriate. Finally, we deal with
revision rejection ($EJ$) or acceptance ($EC$) when in the *Revise*
state. Climbing back up the tree, we see that *Success* in any of the
branches in this or the previous paragraph results in an acknowledgment
message $EK$.

##### Messages That Require More than a Simple Acknowledgment.

Returning to the top portion of the tree in Figure
[\[fig:bt_process_em_messages\]](#fig:bt_process_em_messages){reference-type="ref"
reference="fig:bt_process_em_messages"}, we come to a branch focused on
handling EM messages
when an embargo is no longer viable---in other words, when the case has
reached a point where attacks are occurring, or either the exploit or
the vulnerability has been made public
($q^{cs} \not \in \wc\wc\wc pxa$). This branch takes us to the Terminate
Embargo tree in Figure
[\[fig:bt_terminate\]](#fig:bt_terminate){reference-type="ref"
reference="fig:bt_terminate"}
(§[1.4.2](#sec:terminate_embargo_behavior){reference-type="ref"
reference="sec:terminate_embargo_behavior"}).

Finally, back at the top of Figure
[\[fig:bt_process_em_messages\]](#fig:bt_process_em_messages){reference-type="ref"
reference="fig:bt_process_em_messages"}, when no other branch has
succeeded, we emit an embargo error ($EE$) message to relay the failure.

### Process CS Messages Behavior {#sec:process_cs_messages_bt}

The Process CS
Messages Behavior Tree is shown in Figure
[\[fig:bt_process_cs_messages\]](#fig:bt_process_cs_messages){reference-type="ref"
reference="fig:bt_process_cs_messages"}. We are still working through
the children of the fallback node in Figure
[\[fig:bt_receive_messages\]](#fig:bt_receive_messages){reference-type="ref"
reference="fig:bt_receive_messages"}. And as we've come to expect, a
precondition check leads to a fallback node in which
CS acknowledgement
messages ($CK$) receive no further attention and return *Success*. The
main CS message-handling sequence comes next, with all matching incoming
messages resulting in emission of an acknowledgment message ($CK$).

##### Messages That Change the Participant's Case State.

The tree first handles messages indicating a global
CS change.
Information that the vulnerability has been made public ($CP$) is met
with a transition to the *Public Aware* state in the CS model when
necessary. Similarly, information that an exploit has been made public
forces both the $\mathbf{X}$ and $\mathbf{P}$ transitions, as necessary.
Because the $\mathbf{P}$ transition, should it occur in response to a
$CX$ message, represents possibly new information to the case, it
triggers the emission of a $CP$ message to convey this information to
the other Participants. Likewise, a message indicating attacks underway
triggers the $\mathbf{A}$ transition.

Again, we note that any of the $\mathbf{P}$, $\mathbf{X}$, or
$\mathbf{A}$ transitions in the CS model imply that no new embargo should be
entered, and any existing embargo should be terminated. Hence, the
sequence described in the previous paragraph leads to the embargo
termination described in
§[1.4.2](#sec:terminate_embargo_behavior){reference-type="ref"
reference="sec:terminate_embargo_behavior"}.

##### Messages That Do Not Change the Participant's Case State.

Next, we see that messages indicating *Vendor Awareness* ($CV$), *Fix
Readiness* ($CF$), and *Fix Deployed* ($CD$) are treated as mere status
updates for the Participant because they are recognized and acknowledged
but trigger no further action directly. Recall from
§§[\[sec:rm_cvd\]](#sec:rm_cvd){reference-type="ref"
reference="sec:rm_cvd"} and
[\[sec:vendor_states\]](#sec:vendor_states){reference-type="ref"
reference="sec:vendor_states"} that the
$vfd\wc\wc\wc \rightarrow \dots \rightarrow VFD\wc\wc\wc$ portion of the
CS model is unique
to each Vendor Participant, and similarly, from
§[\[sec:deployer_states\]](#sec:deployer_states){reference-type="ref"
reference="sec:deployer_states"}, that the
$\wc\wc d \wc\wc\wc \rightarrow \wc\wc D \wc\wc\wc$ portion is unique to
each Participant in the Deployer role. Therefore, messages representing
another Participant's status change for this portion of the
CS do not directly
affect the receiving Participant's status. This is not to say that the
Participant might not choose to take some action based on their
knowledge of a Vendor's (or Deployer's) status. Rather, such follow-up
would be expected to occur as part of the Participant's *do work*
process outlined in §[1.5](#sec:do_work){reference-type="ref"
reference="sec:do_work"}.

Following the tree to the right, we encounter the familiar motif of an
error ($CE$) triggering a general inquiry ($GI$) to seek resolution.

In the top of Figure
[\[fig:bt_process_cs_messages\]](#fig:bt_process_cs_messages){reference-type="ref"
reference="fig:bt_process_cs_messages"}, we have handled all expected
messages, so anything else would result in an error condition and
emission of a $CE$ message accordingly.

### Process Other Messages Behavior {#sec:process_gen_messages_bt}

The Process Other Messages Behavior Tree is shown in Figure
[\[fig:bt_process_other_messages\]](#fig:bt_process_other_messages){reference-type="ref"
reference="fig:bt_process_other_messages"}. This tree represents the
final chunk of the fallback node in Figure
[\[fig:bt_receive_messages\]](#fig:bt_receive_messages){reference-type="ref"
reference="fig:bt_receive_messages"}. And here, for the final time, we
see a message type check and that general acknowledgment messages ($GK$)
receive no further attention and return *Success*. General inquiries
($GI$) get at least an acknowledgment, with any follow-up to be handled
by *do work* as described in §[1.5](#sec:do_work){reference-type="ref"
reference="sec:do_work"}. As usual, errors ($GE$) also trigger follow-up
inquiries ($GI$) in the interest of resolution.

##### Chapter Wrap-Up.

In this chapter, we described a complete Behavior Tree for a
CVD Participant
following the formal MPCVD protocol described in Chapter
[\[sec:formal_protocol\]](#sec:formal_protocol){reference-type="ref"
reference="sec:formal_protocol"}. Next, we discuss a few notes regarding
the eventual implementation of this protocol.

[^1]: Corresponding to a Type 3 Zero Day Exploit as defined in §6.5.1 of
    [@householder2021state]
