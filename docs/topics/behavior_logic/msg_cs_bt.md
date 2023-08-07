# Process CS Messages Behavior {#sec:process_cs_messages_bt}

The Process CS
Messages Behavior Tree is shown in Figure
{== [\[fig:bt_process_cs_messages\]](#fig:bt_process_cs_messages){reference-type="ref"
reference="fig:bt_process_cs_messages"} ==}. We are still working through
the children of the fallback node in Figure
{== [\[fig:bt_receive_messages\]](#fig:bt_receive_messages){reference-type="ref"
reference="fig:bt_receive_messages"} ==}. And as we've come to expect, a
precondition check leads to a fallback node in which
CS acknowledgement
messages (_CK_) receive no further attention and return *Success*. The
main CS message-handling sequence comes next, with all matching incoming
messages resulting in emission of an acknowledgment message (_CK_).

## Messages That Change the Participant's Case State.

The tree first handles messages indicating a global
CS change.
Information that the vulnerability has been made public (_CP_) is met
with a transition to the *Public Aware* state in the CS model when
necessary. Similarly, information that an exploit has been made public
forces both the $\mathbf{X}$ and $\mathbf{P}$ transitions, as necessary.
Because the $\mathbf{P}$ transition, should it occur in response to a
_CX_ message, represents possibly new information to the case, it
triggers the emission of a _CP_ message to convey this information to
the other Participants. Likewise, a message indicating attacks underway
triggers the $\mathbf{A}$ transition.

Again, we note that any of the $\mathbf{P}$, $\mathbf{X}$, or
$\mathbf{A}$ transitions in the CS model imply that no new embargo should be
entered, and any existing embargo should be terminated. Hence, the
sequence described in the previous paragraph leads to the embargo
termination described in
§{== [1.4.2](#sec:terminate_embargo_behavior){reference-type="ref"
reference="sec:terminate_embargo_behavior"} ==}.

##### Messages That Do Not Change the Participant's Case State.

Next, we see that messages indicating *Vendor Awareness* (_CV_), *Fix
Readiness* (_CF_), and *Fix Deployed* (_CD_) are treated as mere status
updates for the Participant because they are recognized and acknowledged
but trigger no further action directly. Recall from
§§{== [\[sec:rm_cvd\]](#sec:rm_cvd){reference-type="ref"
reference="sec:rm_cvd"} ==} and
{== [\[sec:vendor_states\]](#sec:vendor_states){reference-type="ref"
reference="sec:vendor_states"} ==} that the
$vfd\cdot\cdot\cdot \rightarrow \dots \rightarrow VFD\cdot\cdot\cdot$ portion of the
CS model is unique
to each Vendor Participant, and similarly, from
§{== [\[sec:deployer_states\]](#sec:deployer_states){reference-type="ref"
reference="sec:deployer_states"} ==}, that the
$\cdot\cdot d \cdot\cdot\cdot \rightarrow \cdot\cdot D \cdot\cdot\cdot$ portion is unique to
each Participant in the Deployer role. Therefore, messages representing
another Participant's status change for this portion of the
CS do not directly
affect the receiving Participant's status. This is not to say that the
Participant might not choose to take some action based on their
knowledge of a Vendor's (or Deployer's) status. Rather, such follow-up
would be expected to occur as part of the Participant's *do work*
process outlined in{== §{== [1.5](#sec:do_work){reference-type="ref"
reference="sec:do_work"} ==} ==}.

Following the tree to the right, we encounter the familiar motif of an
error (_CE_) triggering a general inquiry (_GI_) to seek resolution.

In the top of Figure
{== [\[fig:bt_process_cs_messages\]](#fig:bt_process_cs_messages){reference-type="ref"
reference="fig:bt_process_cs_messages"} ==}, we have handled all expected
messages, so anything else would result in an error condition and
emission of a _CE_ message accordingly.

