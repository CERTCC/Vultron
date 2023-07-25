# Modeling an MPCVD AI Using Behavior Trees {#ch:behavior_trees}

With the formal definition of our proposed [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} protocol behind us, we now turn our
attention to reflect on one of many possible paths toward
implementation. We find that Behavior Trees have a number of desirable
properties when it comes to automating the kinds of complex behaviors
our protocol demands.

Behavior Trees are a way of designing and programming hierarchical
behaviors [@colledanchise2017behavior]. They originated in the computer
gaming industry to develop realistic [AIs]{acronym-label="AI"
acronym-form="plural+full"} to control [NPCs]{acronym-label="NPC"
acronym-form="plural+full"} [@mateas2002behavior; @isla2005halo] in
games. More recently, Behavior Trees have been used in robotics to
create adaptive behaviors using autonomous [AI]{acronym-label="AI"
acronym-form="singular+short"}
agents [@ogren2012increasing; @bagnell2012integrated]. Behavior Trees
offer a high potential for automating complex tasks. Agent processes can
be modeled as sets of behaviors (pre-conditions, actions, and
post-conditions) and the logic that joins them. Behavior Trees offer a
way to organize and describe agent behaviors in a straightforward,
understandable way.

In this chapter, we use Behavior Trees as a method for describing
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} Participant
activities and their interactions with the [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} protocol model from Chapter
[\[sec:formal_protocol\]](#sec:formal_protocol){reference-type="ref"
reference="sec:formal_protocol"}. These behaviors map approximately to
the activities described in the *[CVD]{acronym-label="CVD"
acronym-form="singular+short"} Guide* (e.g., validate report, prioritize
report, create fix, publish report, publish fix, deploy
fix) [@householder2017cert; @cert2019cvd].

If Behavior Trees were merely a notational convention, they would
already have been useful enough to include here to structure the
high-level business logic of the [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} protocol. But they also offer a way to
prototype software agents that reflect the activities of
[CVD]{acronym-label="CVD" acronym-form="singular+short"} Participants.
Because Behavior Trees are inherently hierarchical, they are composable.
Both conditions and actions can be composed into small task-oriented
behaviors, which can, in turn, be composed to represent more complex
agent behaviors. As a result, independent agents using Behavior Trees
can be composed into multi-agent behaviors that achieve goals.

##### A Brief Introduction to Behavior Tree Notation.

Behavior Trees consist of a hierarchy of nodes represented as a
[DAG]{acronym-label="DAG" acronym-form="singular+short"}. A Behavior
Tree execution always begins at the root node, and execution is passed
along the tree by *ticking* each child node according to the logic built
into the tree. When *ticked*, each node does its job and returns one of
three statuses: *Success*, *Failure*, or *Running*. A full introduction
to Behavior Trees can be found in Colledanchise and Ögren's book
*Behavior Trees in Robotics and AI: An
Introduction* [@colledanchise2017behavior].

Node types include

Root

:   has no parent nodes, has one or more child nodes, and can be of any
    of the control-flow types.

:   does not change the state of the world, has no child nodes, and
    returns only *Success* or *Failure*.

:   has no child nodes; performs a task, which might change the state of
    the world; and returns *Success*, *Failure*, or *Running*.

Sequence

:   $\boxed{\rightarrow}$ ticks each child node, returning the last
    *Success* or the first *Failure*, or *Running* if a child returns
    *Running*.

Fallback

:   $\boxed{?}$ ticks each child node, returning the first *Success* or
    the last *Failure*, or *Running* if a child returns *Running*.

Loop

:   $\boxed{\circlearrowright}$ repeatedly ticks child nodes until an
    exit condition is met.

Parallel

:   $\boxed{\rightrightarrows}$ ticks all child nodes simultaneously,
    and returns *Success* when $m$ of $n$ children have returned
    *Success*.

A basic Behavior Tree is shown in Figure
[\[fig:bt_basic\]](#fig:bt_basic){reference-type="ref"
reference="fig:bt_basic"}. In it, we see two motifs that come up through
the remainder of the chapter. On the left side is a Fallback node
($\boxed{?}$), which short-circuits to *Success* when the
$postcondition$ is already met. Otherwise, some activity will occur in
$task_a$ and, assuming that it succeeds, the $postcondition$ is set. As
a result, the fallback node ensures that *Success* means that the
$postcondition$ is met.

On the right side is a sequence ($\boxed{\rightarrow}$) that hinges on a
$precondition$ being met prior to some set of actions being taken.
Assuming the $precondition$ is met, $task_b$ fires and, assuming it
succeeds execution, proceeds to another fallback node. This fallback
node represents a set of tasks in which one only needs to succeed for
the fallback to return *Success*. If $task_c$ succeeds, then $task_d$
does not run.

Behavior Trees are composable---that is, a task node in one tree can be
replaced with a more refined Behavior Tree in another. We leverage this
feature throughout the remainder of this chapter to describe an agent
model for an [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} Participant as a set of nested Behavior
Trees that reflect the protocol described in the previous chapters.

## CVD Behavior Tree {#sec:cvd_bt}

We begin at the root node of the [CVD]{acronym-label="CVD"
acronym-form="singular+short"} Behavior Tree shown in Figure
[\[fig:bt_cvd_process\]](#fig:bt_cvd_process){reference-type="ref"
reference="fig:bt_cvd_process"}. The root node is a simple loop that
continues until an interrupt condition is met, representing the idea
that the [CVD]{acronym-label="CVD" acronym-form="singular+short"}
practice is meant to be continuous. In other words, we are intentionally
not specifying the interrupt condition.

The main sequence is comprised of four main tasks:

-   *Discover vulnerability.* Although not all Participants have the
    ability or motive to discover vulnerabilities, we include it as a
    task here to call out its importance to the overall
    [CVD]{acronym-label="CVD" acronym-form="singular+short"} process. We
    show in §[1.2](#sec:receive_reports_bt){reference-type="ref"
    reference="sec:receive_reports_bt"} that this task returns *Success*
    regardless of whether a vulnerability is found to allow execution to
    pass to the next task.

-   *Receive messages*. All coordination in [CVD]{acronym-label="CVD"
    acronym-form="singular+short"} between Participants is done through
    the exchange of messages, regardless of how those messages are
    conveyed, stored, or presented. The receive messages task represents
    the Participant's response to receiving the various messages defined
    in Chapter
    [\[sec:formal_protocol\]](#sec:formal_protocol){reference-type="ref"
    reference="sec:formal_protocol"}. Due to the degree of detail
    required to cover all the various message types, decomposition of
    this task node is deferred until
    §[1.6](#sec:receive messages){reference-type="ref"
    reference="sec:receive messages"} so we can cover the next two items
    first.

-   *Report management.* This task embodies the [RM]{acronym-label="RM"
    acronym-form="singular+short"} process described in Chapter
    [\[sec:report_management\]](#sec:report_management){reference-type="ref"
    reference="sec:report_management"} as integrated into the
    [MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"}
    protocol of Chapter
    [\[sec:formal_protocol\]](#sec:formal_protocol){reference-type="ref"
    reference="sec:formal_protocol"}. The [RM]{acronym-label="RM"
    acronym-form="singular+short"} Behavior Tree is described in
    §[1.3](#sec:rm_bt){reference-type="ref" reference="sec:rm_bt"}.

-   *Embargo management.* Similarly, this task represents the
    [EM]{acronym-label="EM" acronym-form="singular+short"} process from
    Chapter [\[ch:embargo\]](#ch:embargo){reference-type="ref"
    reference="ch:embargo"} as integrated into the
    [MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"}
    protocol of Chapter
    [\[sec:formal_protocol\]](#sec:formal_protocol){reference-type="ref"
    reference="sec:formal_protocol"}. The [EM]{acronym-label="EM"
    acronym-form="singular+short"} Behavior Tree is decomposed in
    §[1.4](#sec:em_bt){reference-type="ref" reference="sec:em_bt"}

A further breakdown of a number of [CVD]{acronym-label="CVD"
acronym-form="singular+short"} tasks that fall outside the scope of the
formal [MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"}
protocol of Chapter
[\[sec:formal_protocol\]](#sec:formal_protocol){reference-type="ref"
reference="sec:formal_protocol"} can be found in
§[1.5](#sec:do_work){reference-type="ref" reference="sec:do_work"}. In
that section, we examine a number of behaviors that Participants may
include as part of the work they do for reports in the $Accepted$
[RM]{acronym-label="RM" acronym-form="singular+short"} state
($q^{rm}\in A$).

Behaviors and state changes resulting from changes to the
[CS]{acronym-label="CS" acronym-form="singular+short"} model are
scattered throughout the other Behavior Trees where relevant.

## Vulnerability Discovery Behavior {#sec:receive_reports_bt}

[CVD]{acronym-label="CVD" acronym-form="singular+short"} is built on the
idea that vulnerabilities exist to be found. There are two ways for a
[CVD]{acronym-label="CVD" acronym-form="singular+short"} Participant to
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
[CVD]{acronym-label="CVD" acronym-form="singular+short"}
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

## Report Management Behavior Tree {#sec:rm_bt}

A Behavior Tree for the Report Management model is shown in Figure
[\[fig:bt_rm\]](#fig:bt_rm){reference-type="ref" reference="fig:bt_rm"}.
The Report Management process is represented by a Fallback node. Note
that we assume that completing the process will require multiple *ticks*
of the Behavior Tree since each tick can complete, at most, only one
branch.

The first check is to see whether the case is already $Closed$
($q^{rm} \in C$). If that check succeeds, the branch returns *Success*,
and we're done. If it doesn't, we move on to the next branch, which
addresses reports in the *Received* state ($q^{rm} \in R$).

The only action to be taken from $q^{rm} \in R$ is to validate the
report. We address report validation in
§[1.3.1](#sec:report_validation_behavior){reference-type="ref"
reference="sec:report_validation_behavior"}, but, for now, it is
sufficient to say that the validate report behavior returns *Success*
after moving the report to either *Valid* ($q^{rm} \xrightarrow{v} V$)
or *Invalid* ($q^{rm} \xrightarrow{i} I$).

The next branch covers reports in the *Invalid* state ($q^{rm} \in I$).
Here we have two options: either close the report (move to
$q^{rm} \xrightarrow{c} C$,
§[1.3.3](#sec:report_close_behavior){reference-type="ref"
reference="sec:report_close_behavior"}), or retry the validation.

For reports that have reached the *Valid* state ($q^{rm} \in V$), our
only action is to prioritize the report. Report prioritization is
addressed in detail in
§[1.3.2](#sec:report_prioritization_behavior){reference-type="ref"
reference="sec:report_prioritization_behavior"} but returns *Success*
after moving the report to either *Accepted*
($q^{rm} \xrightarrow{a} A$) or *Deferred* ($q^{rm} \xrightarrow{d} D$).

Directing our attention to the lower ($\diamondsuit$) tier of Figure
[\[fig:bt_rm\]](#fig:bt_rm){reference-type="ref" reference="fig:bt_rm"},
we reach behaviors associated with reports that have been both validated
and prioritized. *Deferred* reports ($q^{rm} \in D$) can be *Closed* or
have their priority reevaluated, but otherwise are not expected to
receive additional work.

Similarly, *Accepted* reports ($q^{rm} \in A$) can also be *Closed* or
have their priority reevaluated. However, they are also expected to
receive more effort---the *do work* task node, which we explore further
in §[1.5](#sec:do_work){reference-type="ref" reference="sec:do_work"}.

We are taking advantage of the composability of Behavior Trees to
simplify the presentation. Behaviors that appear in multiple places can
be represented as their own trees. We explore the most relevant of these
subtrees in the next few subsections.

### Report Validation Behavior {#sec:report_validation_behavior}

A Report Validation Behavior Tree is shown in Figure
[\[fig:bt_validate\]](#fig:bt_validate){reference-type="ref"
reference="fig:bt_validate"}. To begin with, if the report is already
*Valid*, no further action is needed from this behavior.

When the report has already been designated as *Invalid*, the necessary
actions depend on whether further information is necessary, or not. If
the current information available in the report is sufficient, no
further action is necessary and the entire behavior returns *Success*.
However, a previous validation pass might have left some indicator that
more information was needed. In that case, execution proceeds to the
sequence in which the *gather info* task runs. If nothing new is found,
the entire branch returns *Success*, and the report remains *Invalid*.
If new information *is* found, though, the branch fails, driving
execution over to the main validation sequence.

The main validation sequence follows when none of the above conditions
have been met. In other words, the validation sequence is triggered when
the report is in *Received* and its validity has never been evaluated or
when the report was originally determined to be *Invalid* but new
information is available to prompt reconsideration. The validation
process shown here is comprised of two main steps: a credibility check
followed by a validity check as outlined in
§[\[sec:rm_state_r\]](#sec:rm_state_r){reference-type="ref"
reference="sec:rm_state_r"}.

As a reminder, a report might be in one of three categories: (a) neither
credible nor valid, (b) credible but invalid, or (c) both credible and
valid. Assuming the report passes both the credibility and validity
checks, it is deemed *Valid*, moved to $q^{rm} \xrightarrow{v} V$, and
an $RV$ message is emitted.

Should either check fail, the validation sequence fails, the report is
deemed *Invalid* and moves (or remains in) $q^{rm} \in I$. In that case,
an $RI$ message is sent when appropriate to update other Participants on
the corresponding state change.

### Report Prioritization Behavior {#sec:report_prioritization_behavior}

The Report Prioritization Behavior Tree is shown in Figure
[\[fig:bt_prioritize\]](#fig:bt_prioritize){reference-type="ref"
reference="fig:bt_prioritize"}. It bears some structural similarity to
the Report Validation Behavior Tree just described: An initial
post-condition check falls back to the main process leading toward
$accept$, which, in turn, falls back to the deferral process. If the
report is already in either the *Accepted* or *Deferred* states and no
new information is available to prompt a change, the behavior ends.

Failing that, we enter the main prioritization sequence. The
preconditions of the main sequence are that either the report has not
yet been prioritized out of the *Valid* state ($q^{rm} \in V$) or new
information has been made available to a report in either
$q^{rm} \in \{ D, A \}$ to trigger a reevaluation.

Assuming the preconditions are met, the report priority is evaluated.
For example, a Participant using SSVC [@spring2021ssvc] could insert
that process here. The evaluation task is expected to always set the
report priority. The subsequent check returns *Failure* on a defer
priority or *Success* on any non-deferral priority. On *Success*, an
*accept* task is included as a placeholder for any intake process that a
Participant might have for *Accepted* reports. Assuming that it
succeeds, the report is explicitly moved to the *Accepted*
($q^{rm} \xrightarrow{a} A$) state, and an $RA$ message is emitted.

Should any item in the main sequence fail, the case is deferred, its
state set to $q^{rm} \xrightarrow{d} D$, and an $RD$ message is emitted
accordingly. Similarly, a *defer* task is included as a callback
placeholder.

### Report Closure Behavior {#sec:report_close_behavior}

The Report Closure Behavior Tree is shown in Figure
[\[fig:bt_close\]](#fig:bt_close){reference-type="ref"
reference="fig:bt_close"}. As usual, the post-condition is checked
before proceeding. If the case is already *Closed* ($q^{rm} \in C$),
we're done. Otherwise, the main close sequence begins with a check for
whether the report closure criteria have been met. Report closure
criteria are Participant specific and are, therefore, out of scope for
this report. Nevertheless, once those closure criteria are met, the
actual *close report* task is activated (e.g., an `OnClose` callback).
The sequence ends with setting the state to *Closed*
($q^{rm} \xrightarrow{c} C$) and emitting an $RC$ message.

## Embargo Management Behavior Tree {#sec:em_bt}

The Embargo Management Behavior Tree is shown in Figure
[\[fig:bt_em_2\]](#fig:bt_em_2){reference-type="ref"
reference="fig:bt_em_2"}. It follows the state transition function in
Table [\[tab:em_send\]](#tab:em_send){reference-type="ref"
reference="tab:em_send"}. Recall that the EM process begins in the
$q^{em} \in N$ state and ends in one of two states:

-   in the *eXited* ($q^{em} \in X$) state after having established an
    *Active* embargo, or

-   in the *None* ($q^{em} \in N$) state after having exhausted all
    attempts to reach an agreement

The tree starts with a check to see whether no report has arrived or
whether the report has already *Closed* ($q^{rm} \in \{S{,}C\}$). If
either of these conditions is met, no further effort is needed, and the
tree succeeds. Next, the tree checks whether the embargo has already
*eXited* ($q^{em} \in X$). If it has, that leads the tree to succeed.
Failing that, the treat checks to see if the case has moved outside the
"habitable zone" for embargoes. The ${q^{cs}\not\in\wc\wc\wc pxa}$
condition is true when attacks have been observed, an exploit has been
made public, or information about the vulnerability has been made
public. If one of those conditions is met and the embargo state is
*None* ($q^{em} \in N$), the check returns *Success*, and the tree
terminates, consistent with
§[\[sec:entering_an_embargo\]](#sec:entering_an_embargo){reference-type="ref"
reference="sec:entering_an_embargo"}.

Otherwise, we continue through each remaining [EM]{acronym-label="EM"
acronym-form="singular+short"} state. When there is no embargo and there
are no outstanding proposals ($q^{em} \in N$), the only options are to
either stop trying or propose a new embargo. The decision to stop trying
to achieve an embargo is left to individual Participants, although we
did provide some relevant guidance in
§[\[sec:negotiating_embargoes\]](#sec:negotiating_embargoes){reference-type="ref"
reference="sec:negotiating_embargoes"}.

When there is an outstanding embargo proposal ($q^{em} \in P$), we first
attempt the terminate task. We shall see in
§[1.4.2](#sec:terminate_embargo_behavior){reference-type="ref"
reference="sec:terminate_embargo_behavior"} that this task returns
*Success* if there is a reason for ${q^{em} \in P \xrightarrow{r} N}$.

Otherwise we proceed to the bottom ($\clubsuit$) tier of Figure
[\[fig:bt_em_2\]](#fig:bt_em_2){reference-type="ref"
reference="fig:bt_em_2"} to evaluate and possibly accept the proposal.
Acceptance leads to an [EM]{acronym-label="EM"
acronym-form="singular+short"} state transition to $q^{em} \in A$ and
emission of an $EA$ message.

On the other hand, the proposed terms may not be acceptable. In this
case, the Participant might be willing to offer a counterproposal. The
counterproposal is covered by the propose behavior described in
§[1.4.1](#sec:propose_embargo_behavior){reference-type="ref"
reference="sec:propose_embargo_behavior"}.

Assuming neither of these succeeds, we return to the top tier of Figure
[\[fig:bt_em_2\]](#fig:bt_em_2){reference-type="ref"
reference="fig:bt_em_2"} and reject the proposal, returning to
$q^{em} \in N$ and emitting a corresponding $ER$ message.

This brings us to the middle ($\diamondsuit$) tier of Figure
[\[fig:bt_em_2\]](#fig:bt_em_2){reference-type="ref"
reference="fig:bt_em_2"}. The process within the *Active*
($q^{em} \in A$) state is similarly straightforward. If there is reason
to terminate the embargo, do so. Otherwise, either the current embargo
terms are acceptable, or a new embargo should be proposed.

Finally, we handle the *Revise* [EM]{acronym-label="EM"
acronym-form="singular+short"} state ($q^{em} \in R$). The structure of
this branch mirrors that of the *Proposed* state discussed above. Again,
we check to see if there is cause to terminate doing so, if needed. If
termination is not indicated, we proceed once again to the bottom
($\clubsuit$) tier to evaluate the proposed revision, either accepting
or countering the proposal. When neither of these succeed, the revision
is rejected and the [EM]{acronym-label="EM"
acronym-form="singular+short"} state returns to $q^{em} \in A$ with the
original embargo terms intact. An $EJ$ message conveys this information
to the other Participants.

### Propose Embargo Behavior {#sec:propose_embargo_behavior}

The Propose Embargo Behavior Tree is shown in Figure
[\[fig:bt_propose\]](#fig:bt_propose){reference-type="ref"
reference="fig:bt_propose"}. It consists of a sequence that begins with
a check for embargo viability as outlined in
§[\[sec:entering_an_embargo\]](#sec:entering_an_embargo){reference-type="ref"
reference="sec:entering_an_embargo"}. Once the checks succeed, it
proceeds to selecting embargo terms to propose. Implementations of this
task might simply draw from a default policy, as in
§[\[sec:default_embargoes\]](#sec:default_embargoes){reference-type="ref"
reference="sec:default_embargoes"}, or it might be a case-specific
decision made by a Participant. Embargo terms can be proposed from any
of the non-*eXited* states ($q^{em} \in \{N,P,A,R\}$). If a new or
revised embargo has already been proposed, the tree then checks whether
a counterproposal is desired. Assuming it is not, no proposal is made,
and the behavior succeeds. Otherwise, proposals from state
$q^{em} \in N$ emit $EP$ and transition $q^{em} \xrightarrow{p} P$,
whereas those from $q^{em} \in A$ emit $EV$ and move to
$q^{em} \xrightarrow{p} R$. Proposals from states $q^{em} \in P$ or
$q^{em} \in R$ represent counterproposals and, therefore, do not change
the EM state. They do, however, emit $EP$ or $EV$ messages as
appropriate.

### Terminate Embargo Behavior {#sec:terminate_embargo_behavior}

The Terminate Embargo Behavior Tree is shown in Figure
[\[fig:bt_terminate\]](#fig:bt_terminate){reference-type="ref"
reference="fig:bt_terminate"}. It consists of two major behaviors
depending on whether an embargo has been established or not.

If the [EM]{acronym-label="EM" acronym-form="singular+short"} state is
*None* or *eXited*, ($q^{em} \in \{N{,}X\}$), the tree succeeds
immediately. The next node handles the scenario where no embargo has
been established. The behavior descends into a sequence that checks
whether we are in $Propose$ ($q^{em} \in P$). If we are, we check to see
if there is a reason to exit the embargo negotiation process. One such
reason is that the case state is outside the embargo "habitable zone,"
but there may be others that we leave unspecified. If any reason is
found, then the proposal is rejected, the state returns to *None*, and
an $ER$ message is sent.

Should that branch fail, we still need to handle the situation where an
embargo has already been established. Following a confirmation that we
are in either *Active* or *Revise*, we again look for reasons to exit,
this time adding the possibility of timer expiration to the conditions
explicitly called out. Terminating an existing embargo might have some
other teardown procedures to be completed, which we represent as the
*exit embargo* task. Finally, the [EM]{acronym-label="EM"
acronym-form="singular+short"} state is updated to *eXited* and an $ET$
message is emitted.

The Terminate Embargo Behavior Tree appears in multiple locations in the
larger tree. We will encounter it again as a possible response to
evidence collected via threat monitoring
(§[1.5.5](#sec:monitor_threats_bt){reference-type="ref"
reference="sec:monitor_threats_bt"}) as well as in response to certain
[CS]{acronym-label="CS" acronym-form="singular+short"} or
[EM]{acronym-label="EM" acronym-form="singular+short"} messages in
states when an embargo is no longer viable
(§[\[fig:bt_process_cs_messages\]](#fig:bt_process_cs_messages){reference-type="ref"
reference="fig:bt_process_cs_messages"} and
§[\[fig:bt_process_em_messages\]](#fig:bt_process_em_messages){reference-type="ref"
reference="fig:bt_process_em_messages"}, respectively).

## Do Work Behavior {#sec:do_work}

Although it is not directly addressed by the formal
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} protocol
defined in Chapter
[\[sec:formal_protocol\]](#sec:formal_protocol){reference-type="ref"
reference="sec:formal_protocol"}, the *do work* node of the
[RM]{acronym-label="RM" acronym-form="singular+short"} Behavior Tree in
Figure [\[fig:bt_rm\]](#fig:bt_rm){reference-type="ref"
reference="fig:bt_rm"} and §[1.3](#sec:rm_bt){reference-type="ref"
reference="sec:rm_bt"} is where much of the [CVD]{acronym-label="CVD"
acronym-form="singular+short"} effort happens. As a result, it is worth
spending some time reviewing what some of the underlying work actually
entails.

In this section, we will expand on the set of behaviors shown in Figure
[\[fig:bt_do_work\]](#fig:bt_do_work){reference-type="ref"
reference="fig:bt_do_work"}. Specifically, we will cover the following
tasks, each in its own subsection.

-   Deployment

-   Developing a fix

-   Reporting to others

-   Publication

-   Monitoring threats

-   Assigning CVE IDs

-   Acquiring exploits

The *other work* task is included as a placeholder for any
Participant-specific tasks not represented here.

Note that Figure
[\[fig:bt_do_work\]](#fig:bt_do_work){reference-type="ref"
reference="fig:bt_do_work"} models this behavior as a parallel Behavior
Tree node, although we intentionally do not specify any *Success*
criteria regarding what fraction of its children must succeed. Decisions
about which (and how many) of the following tasks are necessary for a
Participant to complete work on their $Accepted$
[CVD]{acronym-label="CVD" acronym-form="singular+short"} cases are left
to the discretion of individual Participants.

### Deployment Behavior {#sec:deployment_bt}

The Deployment Behavior Tree is shown in Figure
[\[fig:bt_deployment\]](#fig:bt_deployment){reference-type="ref"
reference="fig:bt_deployment"}. The goal of this behavior is either for
the case to reach the $q^{cs} \in D$ state or for the Participant to be
comfortable with remaining in a *Deferred* deployment state.

Assuming neither of these conditions has been met, the main deployment
sequence falls to the Developer role. It consists of two subprocesses:
prioritize deployment and deploy. The prioritize deployment behavior is
shown in the fallback node in the center of Figure
[\[fig:bt_deployment\]](#fig:bt_deployment){reference-type="ref"
reference="fig:bt_deployment"}. The subgoal is for the deployment
priority to be established, as indicated by the Deployer's
[RM]{acronym-label="RM" acronym-form="singular+short"} state
$q^{rm} \in \{D,A\}$. For example, a Deployer might use the SSVC
Deployer Tree [@spring2021ssvc] to decide whether (and when) to deploy a
fix or mitigation. If the deployment priority evaluation indicates
further action is needed, the report management state is set to
$q^{rm} \in A$. An $RA$ message is emitted, and the overall
prioritization behavior succeeds. Otherwise, when the deployment is
*Deferred*, it results in a transition to state $q^{rm} \in D$ and
emission of an $RD$ message.

The deploy behavior is shown in the diamond tier ($\diamondsuit$) of
Figure [\[fig:bt_deployment\]](#fig:bt_deployment){reference-type="ref"
reference="fig:bt_deployment"}. It short-circuits to *Success* if either
the deployment is *Deferred* or has already occurred. The main sequence
can fire in two cases:

1.  when the Deployer is also the Vendor and a fix is ready
    ($q^{cs} \in F$)

2.  when the Deployer is not the Vendor but the fix is both ready and
    public ($q^{cs} \in P$ and $q^{cs} \in F$)

Assuming either of these conditions is met, the deploy fix task can run,
the case status is updated to $q^{cs} \in D$, and $CD$ emits on
*Success*. Should the deployment sequence fail for any reason, a
fallback is possible if undeployed mitigations are available.

Finally, returning to the top part of the tree, Participants might
choose to monitor the deployment process should they have the need to.

### Fix Development Behavior {#sec:fix_dev_bt}

The Fix Development Behavior Tree is shown in Figure
[\[fig:bt_fix_development\]](#fig:bt_fix_development){reference-type="ref"
reference="fig:bt_fix_development"}. Fix development is relegated to the
Vendor role, so Non-Vendors just return *Success* since they have
nothing further to do. For Vendors, if a fix is ready (i.e., the case is
in $q^{cs} \in VF\wc\wc\wc\wc$), the tree returns *Success*. Otherwise,
engaged Vendors ($q^{rm} \in A$) can create fixes, set
$q^{cs} \in Vfd\wc\wc\wc \xrightarrow{\mathbf{F}} VFd\wc\wc\wc$ and emit
$CF$ upon completion.

### Reporting Behavior {#sec:reporting_bt}

The *CERT Guide to Coordinated Vulnerability Disclosure* describes the
reporting phase as the process of identifying parties that need to be
informed about the vulnerability and then notifying them
[@householder2017cert]. Reporting only works if the intended recipient
has the ability to receive reports, as outlined in
§[1.2](#sec:receive_reports_bt){reference-type="ref"
reference="sec:receive_reports_bt"}.

The Reporting Behavior Tree is shown in Figure
[\[fig:bt_reporting\]](#fig:bt_reporting){reference-type="ref"
reference="fig:bt_reporting"}. The tree describes a Participant that
performs reporting until either their effort limit is met, or they run
out of Participants to notify.

#### Identify Participants Behavior {#sec:identify_participants}

The Identify Participants Behavior Tree, shown in Figure
[\[fig:bt_identify_participants\]](#fig:bt_identify_participants){reference-type="ref"
reference="fig:bt_identify_participants"}, ends when all relevant
parties have been identified. Until that condition is met, the
Participant can proceed with identifying Vendors, Coordinators, or other
parties relevant to the coordination of the case. Note that we are
intentionally avoiding setting any requirements about *who* is relevant
to a case since we leave that to each Participant's judgment.

#### Notify Others Behavior {#sec:notify_others}

The Notify Others Behavior Tree is shown in Figure
[\[fig:bt_notify_others\]](#fig:bt_notify_others){reference-type="ref"
reference="fig:bt_notify_others"}. Its goal is for all intended
recipients to receive the report, thereby reaching the $q^{rm} \in R$
state. Each pass through this part of the tree chooses a Participant
from a list of eligible recipients constructed in the Identify
Participants Behavior. The method for choosing the recipient is left
unspecified since Participants can prioritize recipients how they see
fit.

The process proceeds to clean up the eligible recipients list when
either the recipient is already believed to be in $q^{rm} \in R$ or if
the effort expended in trying to reach the recipient has exceeded the
Participant's limit. Such limits are entirely left to the discretion of
each Participant. If the chosen recipient is pruned by this branch, the
branch returns *Success*.

If the chosen recipient was not pruned, then the cleanup branch fails
and execution transfers to the second branch to notify the recipient.
The first step in the notification branch is a check for an existing
embargo. If the embargo management state is one of
$q^{em} \in \{ N,P,X\}$, there is no active embargo, and the Participant
can proceed with notification. Otherwise, in the case of an already
active embargo (i.e., $q^{em} \in \{A,R\}$), there is an additional
check to ensure that the potential recipient's policy is compatible with
any existing embargo. This check allows for a reporting Participant to
skip a recipient if they are likely to cause premature termination of an
extant embargo.

Once at least one of these checks is passed, the notification sequence
proceeds through finding the recipient's contact information, sending
the report, and updating the Participant's knowledge of the recipient's
report management state.

### Publication Behavior {#sec:publication_bt}

The Publication Behavior Tree is shown in Figure
[\[fig:bt_publication\]](#fig:bt_publication){reference-type="ref"
reference="fig:bt_publication"}. It begins by ensuring that the
Participant knows what they intend to publish, followed by a check to
see if that publication has been achieved. Assuming that work remains to
be done, the main publish sequence commences on the right-hand branch.

The process begins with preparation for publication, described in
§[1.5.4.1](#sec:prepare_publication_bt){reference-type="ref"
reference="sec:prepare_publication_bt"}, followed by a pre-publication
embargo check. This behavior is a simple check to ensure that no embargo
remains active prior to publication. Note that the embargo management
process may result in early termination of an existing embargo if the
Participant has sufficient cause to do so. (See the detailed description
of the EM behavior in §[1.4](#sec:em_bt){reference-type="ref"
reference="sec:em_bt"}.)

Once these subprocesses complete, the publish task fires, the case state
is updated to $q^{cs} \in P$, and a $CP$ message emits.

#### Prepare Publication Behavior {#sec:prepare_publication_bt}

The Prepare Publication Behavior Tree is shown in Figure
[\[fig:bt_prepare_publication\]](#fig:bt_prepare_publication){reference-type="ref"
reference="fig:bt_prepare_publication"}. There are separate branches for
publishing exploits, fixes, and reports. The publish exploit branch
succeeds if either no exploit publication is intended, if it is intended
and ready, or if it can be acquired and prepared for publication. The
publish fix branch succeeds if the Participant does not intend to
publish a fix (e.g., if they are not the Vendor), if a fix is ready, or
if it can be developed and prepared for publication. The publish report
branch is the simplest and succeeds if either no publication is intended
or if the report is ready to go.

Once all three branches have completed, the behavior returns *Success*.

### Monitor Threats Behavior {#sec:monitor_threats_bt}

The Monitor Threats Behavior Tree is shown in Figure
[\[fig:bt_monitor_threats\]](#fig:bt_monitor_threats){reference-type="ref"
reference="fig:bt_monitor_threats"}. For our purposes, monitoring
consists of a set of parallel tasks, any one of which can lead to
embargo termination. The three conditions of interest are taken straight
from the embargo exit criteria:

-   If attacks are observed, the $q^{cs} \xrightarrow{\mathbf{A}} A$
    transition occurs, and a $CA$ message is emitted.

-   If a public exploit is observed, the
    $q^{cs} \xrightarrow{\mathbf{X}} X$ transition occurs, and a $CX$
    message is emitted. In the special case where the exploit is made
    public prior to the vulnerability itself being made public,[^1]
    there is an additional $q^{cs} \xrightarrow{\mathbf{P}} P$
    transition and $CP$ emission.

-   Finally, if the vulnerability information has been made public, then
    the $q^{cs} \xrightarrow{\mathbf{P}} P$ and emits $CP$.

In the event that one or more of these events is detected, the terminate
embargo behavior is triggered.

There are many other good reasons to monitor and maintain awareness of
cybersecurity threats. The behavior shown here is intended as a minimal
set of things that [CVD]{acronym-label="CVD"
acronym-form="singular+short"} Participants should watch out for in the
course of performing their [CVD]{acronym-label="CVD"
acronym-form="singular+short"} practice.

### CVE ID Assignment Behavior {#sec:assign_id_bt}

Many [CVD]{acronym-label="CVD" acronym-form="singular+short"}
practitioners want to assign identifiers to the vulnerabilities they
coordinate. The most common of these is a [CVE]{acronym-label="CVE"
acronym-form="singular+short"} ID, so we provide an example CVE ID
Assignment Behavior Tree, shown in Figure
[\[fig:bt_cve_assignment\]](#fig:bt_cve_assignment){reference-type="ref"
reference="fig:bt_cve_assignment"}. While this tree is constructed
around the [CVE]{acronym-label="CVE" acronym-form="singular+short"} ID
assignment process, it could be easily adapted to any other identifier
process as well.

The goal is to end with an ID assigned. If that has not yet happened,
the first check is whether the vulnerability is in scope for an ID
assignment. If it is, the Participant might be able to assign IDs
directly, assuming they are a [CNA]{acronym-label="CNA"
acronym-form="singular+short"} and the vulnerability meets the criteria
for assigning IDs.

Otherwise, if the Participant is not a [CNA]{acronym-label="CNA"
acronym-form="singular+short"}, they will have to request an ID from a
[CNA]{acronym-label="CNA" acronym-form="singular+short"}.

Should both assignment branches fail, the behavior fails. Otherwise, as
long as one of them succeeds, the behavior succeeds.

### Acquire Exploit Behavior {#sec:exploit_acq_bt}

Some Vendors or other [CVD]{acronym-label="CVD"
acronym-form="singular+short"} Participants might require a
proof-of-concept exploit to accompany an incoming report for it to pass
their validation checks. To that end, an Acquire Exploit Behavior Tree
is shown in Figure
[\[fig:bt_exploit_acquisition\]](#fig:bt_exploit_acquisition){reference-type="ref"
reference="fig:bt_exploit_acquisition"}. The goal of this behavior is
for the Participant to be in possession of an exploit.

If the Participant does not already have one, the main acquisition
sequence is triggered. The sequence begins by ensuring that the exploit
acquisition activity has sufficient priority to continue. If it does,
the Participant has one of three options to choose from: they can find
one somewhere else, develop it themselves, or pay someone for the
privilege.

The overall behavior returns *Success* when either an exploit is
acquired or when one is not desired and is therefore deferred. It can
fail in the scenario where an exploit is desired but not acquired.

## Receiving and Processing Messages Behavior {#sec:receive messages}

Now we return to the [CVD]{acronym-label="CVD"
acronym-form="singular+short"} Behavior Tree in Figure
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
assigned yet, implying they are in the [RM]{acronym-label="RM"
acronym-form="singular+short"} *Start* state ($q^{rm} \in S$).
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

The Process [RM]{acronym-label="RM" acronym-form="singular+short"}
Messages Behavior Tree is shown in Figure
[\[fig:bt_process_rm_messages\]](#fig:bt_process_rm_messages){reference-type="ref"
reference="fig:bt_process_rm_messages"}. It is a child of the fallback
node started in Figure
[\[fig:bt_receive_messages\]](#fig:bt_receive_messages){reference-type="ref"
reference="fig:bt_receive_messages"}. Beginning with a precondition
check for any [RM]{acronym-label="RM" acronym-form="singular+short"}
message type, the tree proceeds to a fallback node.
[RM]{acronym-label="RM" acronym-form="singular+short"} acknowledgment
messages ($RK$) receive no further attention and return *Success*.

Next comes the main [RM]{acronym-label="RM"
acronym-form="singular+short"} message processing sequence. A fallback
node covers three major cases:

-   First comes a sequence that handles new reports ($RS$ when
    $q^{rm} \in S$). This branch changes the recipient's
    [RM]{acronym-label="RM" acronym-form="singular+short"} state
    regardless of the Participant's role. If the Participant happens to
    be a Vendor and the Vendor was previously unaware of the
    vulnerability described by the report, the Vendor would also note
    the [CS]{acronym-label="CS" acronym-form="singular+short"}
    transition from $q^{cs} \in vfd \xrightarrow{\mathbf{V}} Vfd$ and
    emit a corresponding $CV$ message.

-   Next, we see that an [RM]{acronym-label="RM"
    acronym-form="singular+short"} Error ($RE$) results in the emission
    of a general inquiry ($GI$) for Participants to sort out what the
    problem is, along with an $RK$ to acknowledge receipt of the error.

-   Finally, recall that the [RM]{acronym-label="RM"
    acronym-form="singular+short"} process is unique to each
    [CVD]{acronym-label="CVD" acronym-form="singular+short"}
    Participant, so most of the remaining [RM]{acronym-label="RM"
    acronym-form="singular+short"} messages are simply informational
    messages about other Participants' statuses that do not directly
    affect the receiver's status. Therefore, if there is already an
    associated case ($q^{rm} \not\in S$), the recipient might update
    their record of the sender's state, but no further action is needed.

For all three cases, an $RK$ message acknowledges receipt of the
message. Any unhandled message results in an $RE$ response, indicating
an error.

### Process EM Messages Behavior {#sec:process_em_messages_bt}

The Process [EM]{acronym-label="EM" acronym-form="singular+short"}
Messages Behavior Tree is shown in Figure
[\[fig:bt_process_em_messages\]](#fig:bt_process_em_messages){reference-type="ref"
reference="fig:bt_process_em_messages"}. As above, it is a child of the
fallback node started in Figure
[\[fig:bt_receive_messages\]](#fig:bt_receive_messages){reference-type="ref"
reference="fig:bt_receive_messages"}. A precondition check for
[EM]{acronym-label="EM" acronym-form="singular+short"} message types is
followed by a fallback node. [EM]{acronym-label="EM"
acronym-form="singular+short"} acknowledgment messages ($EK$) receive no
further attention and return *Success*.

##### Messages That Lead to a Simple Acknowledgment.

Next is a branch handling all the messages that will result in a simple
acknowledgment ($EK$). First, we handle embargo error messages ($EE$),
which additionally trigger a general inquiry ($GI$) message to attempt
to resolve the problem. Second are embargo termination messages ($ET$).
If the Participant is already in the [EM]{acronym-label="EM"
acronym-form="singular+short"} *eXited* state ($X$), no further action
is taken (aside from the $EK$). Otherwise, if the Participant is in
either *Active* or *Revise* [EM]{acronym-label="EM"
acronym-form="singular+short"} states, the $ET$ message triggers a state
transition $q^{em} \xrightarrow{t} X$. Embargo rejections are handled
next in a simple sequence that returns the state from *Proposed* to
*None*.

The final chunk of the simple acknowledge branch handles
[EM]{acronym-label="EM" acronym-form="singular+short"} messages received
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
handling [EM]{acronym-label="EM" acronym-form="singular+short"} messages
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

The Process [CS]{acronym-label="CS" acronym-form="singular+short"}
Messages Behavior Tree is shown in Figure
[\[fig:bt_process_cs_messages\]](#fig:bt_process_cs_messages){reference-type="ref"
reference="fig:bt_process_cs_messages"}. We are still working through
the children of the fallback node in Figure
[\[fig:bt_receive_messages\]](#fig:bt_receive_messages){reference-type="ref"
reference="fig:bt_receive_messages"}. And as we've come to expect, a
precondition check leads to a fallback node in which
[CS]{acronym-label="CS" acronym-form="singular+short"} acknowledgement
messages ($CK$) receive no further attention and return *Success*. The
main CS message-handling sequence comes next, with all matching incoming
messages resulting in emission of an acknowledgment message ($CK$).

##### Messages That Change the Participant's Case State.

The tree first handles messages indicating a global
[CS]{acronym-label="CS" acronym-form="singular+short"} change.
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
$\mathbf{A}$ transitions in the [CS]{acronym-label="CS"
acronym-form="singular+short"} model imply that no new embargo should be
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
[CS]{acronym-label="CS" acronym-form="singular+short"} model is unique
to each Vendor Participant, and similarly, from
§[\[sec:deployer_states\]](#sec:deployer_states){reference-type="ref"
reference="sec:deployer_states"}, that the
$\wc\wc d \wc\wc\wc \rightarrow \wc\wc D \wc\wc\wc$ portion is unique to
each Participant in the Deployer role. Therefore, messages representing
another Participant's status change for this portion of the
[CS]{acronym-label="CS" acronym-form="singular+short"} do not directly
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
[CVD]{acronym-label="CVD" acronym-form="singular+short"} Participant
following the formal [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} protocol described in Chapter
[\[sec:formal_protocol\]](#sec:formal_protocol){reference-type="ref"
reference="sec:formal_protocol"}. Next, we discuss a few notes regarding
the eventual implementation of this protocol.

[^1]: Corresponding to a Type 3 Zero Day Exploit as defined in §6.5.1 of
    [@householder2021state]
