# Process Other Messages Behavior {#sec:process_gen_messages_bt}

The Process Other Messages Behavior Tree is shown in Figure
{== [\[fig:bt_process_other_messages\]](#fig:bt_process_other_messages){reference-type="ref"
reference="fig:bt_process_other_messages"} ==}. This tree represents the
final chunk of the fallback node in Figure
{== [\[fig:bt_receive_messages\]](#fig:bt_receive_messages){reference-type="ref"
reference="fig:bt_receive_messages"} ==}. And here, for the final time, we
see a message type check and that general acknowledgment messages (_GK_)
receive no further attention and return *Success*. General inquiries
(_GI_) get at least an acknowledgment, with any follow-up to be handled
by *do work* as described in{== §{== [1.5](#sec:do_work){reference-type="ref"
reference="sec:do_work"} ==} ==}. As usual, errors (_GE_) also trigger follow-up
inquiries (_GI_) in the interest of resolution.

