# Reporting Behavior

The [*CERT Guide to Coordinated Vulnerability Disclosure*](https://vuls.cert.org/confluence/display/CVD)
describes the reporting phase as the process of identifying parties that need to be informed about the vulnerability
and then notifying them.
Reporting only works if the intended recipient has the ability to receive reports, as outlined in
our introduction of the [RM _Received_ state](/topics/process_models/rm/#the-received-r-state).

The Reporting Behavior Tree is shown in the figure below.

```mermaid
---
title: Reporting Behavior Tree
---
flowchart LR
    loop["#8634;"]
    identify_participants["identify participants"]
    loop --> identify_participants
    notify_others["notify others"]
    loop --> notify_others
```

The tree describes a Participant that performs reporting until either their effort limit is met, or they run out of 
Participants to notify.

## Identify Participants Behavior

!!! tip inline end "Participant Inclusion Choices are left to Participants"
    
    Note that we are intentionally avoiding setting any requirements about *who* is relevant to a case.
    We leave that decision to each Participant's judgment.

The Identify Participants Behavior Tree, shown in the following diagram, ends when all relevant parties have been 
identified. 
Until that condition is met, the Participant can proceed with identifying Vendors, Coordinators, or other
parties relevant to the coordination of the case.

```mermaid
---
title: Identify Participants Behavior Tree
---
flowchart LR
    fb["?"]
    all_known(["all relevant<br/>parties known?"])
    fb --> all_known
    seq["&rarr;"]
    fb --> seq
    identify_vendor["identify vendor(s)"]
    seq --> identify_vendor
    identify_coordinator["identify coordinator(s)"]
    seq --> identify_coordinator
    identify_other["identify other(s)"]
    seq --> identify_other
```

## Notify Others Behavior {#sec:notify_others}

The Notify Others Behavior Tree is shown in the figure below.

```mermaid
---
title: Notify Others Behavior Tree
---
flowchart LR
    fb["?"]
    all_notified(["all notified<br/>RM not in S?"])
    fb --> all_notified
    seq["&rarr;"]
    fb --> seq
    choose_recipient["choose recipient"]
    seq --> choose_recipient
    fb2["?"]
    seq --> fb2
    seq2["&rarr;"]
    fb2 --> seq2
    fb3["?"]
    seq2 --> fb3
    recp_not_in_S(["recipient RM not in S?"])
    fb3 --> recp_not_in_S
    effort_exceeded(["effort limit<br/>exceeded?"])
    fb3 --> effort_exceeded
    remove_recp["remove recipient"]
    seq2 --> remove_recp
    seq3["&rarr;"]
    fb2 --> seq3
    fb4["?"]
    seq3 --> fb4
    em_n_p_x(["EM in N,P,X?"])
    fb4 --> em_n_p_x
    seq4["&rarr;"]
    fb4 --> seq4
    em_a_r(["EM in A,R?"])
    seq4 --> em_a_r
    rcp_policy_compatible(["recipient policy<br/>compatible?"])
    seq4 --> rcp_policy_compatible
    find_contact["find contact info"]
    seq3 --> find_contact
    send_report["send report</br>(emit RS)"]
    seq3 --> send_report
    recp_rm_to_r["recipient RM &rarr; R"]
    seq3 --> recp_rm_to_r
```

The goal of this behavior tree is for all intended recipients to receive the report, thereby reaching the $q^{rm} \in R$ state.
Each pass through this part of the tree chooses a Participant from a list of eligible recipients constructed in the Identify
Participants Behavior.
The method for choosing the recipient is left unspecified since Participants can prioritize recipients how they see fit.

The process proceeds to clean up the eligible recipients list when either the recipient is already believed to be in 
$q^{rm} \in R$ or if the effort expended in trying to reach the recipient has exceeded the Participant's limit.
Such limits are entirely left to the discretion of each Participant.
If the chosen recipient is pruned by this branch, the branch returns *Success*.

If the chosen recipient was not pruned, then the cleanup branch fails and execution transfers to the second branch to 
notify the recipient.
The first step in the notification branch is a check for an existing embargo.
If the embargo management state is one of $q^{em} \in \{ N,P,X\}$, there is no active embargo, and the Participant
can proceed with notification.

Otherwise, in the case of an already active embargo (i.e., $q^{em} \in \{A,R\}$), there is an additional check to
ensure that the potential recipient's policy is compatible with any existing embargo.
This check allows for a reporting Participant to skip a recipient if they are likely to cause premature termination of 
an extant embargo.

Once at least one of these checks is passed, the notification sequence proceeds through finding the recipient's contact
information, sending the report, and updating the Participant's knowledge of the recipient's report management state.
