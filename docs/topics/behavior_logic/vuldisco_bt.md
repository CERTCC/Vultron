## Vulnerability Discovery Behavior {#sec:receive_reports_bt}

CVD is built on the
idea that vulnerabilities exist to be found. There are two ways for a
CVD Participant to
find out about a vulnerability. Either they discover it themselves, or
they hear about it from someone else. The discovery behavior is modeled
by the Discover Vulnerability Behavior Tree shown in Figure
[\[fig:bt_become_aware\]](#fig:bt_become_aware){reference-type="ref"
reference="fig:bt_become_aware"}. External reports are covered in
§[1.6.1](#sec:process_rm_messages_bt){reference-type="ref"
reference="sec:process_rm_messages_bt"}.

The goal of the Discover Vulnerability Behavior is for the Participant
to end up outside of the *Start* state of the Report Management process
($q^{rm} \not \in S$). Assuming this has not already occurred, the
discovery sequence is followed. If the Participant has both the means
and the motive to find a vulnerability, they might discover it
themselves. Should this succeed, the branch sets
$q^{rm} \in S \xrightarrow{r} R$ and returns *Success*. We also show a
report submission ($RS$) message being emitted as a reminder that even
internally discovered vulnerabilities can trigger the
CVD
process---although, at the point of discovery, the Finder is the only
Participant, so the $RS$ message in this situation might be an internal
message within the Finder organization (at most).

Should no discovery occur, the branch returns *Success* so that the
parent process in Figure [1.1](#sec:cvd_bt){reference-type="ref"
reference="sec:cvd_bt"} can proceed to receive messages from others.
Because of the amount of detail necessary to describe the *receive
messages* behavior, we defer it to
§[1.6](#sec:receive messages){reference-type="ref"
reference="sec:receive messages"}. Before we proceed, it is sufficient
to know that a new report arriving in the *receive messages* behavior
sets $q^{rm} \in S \xrightarrow{r} R$ and returns *Success*.



