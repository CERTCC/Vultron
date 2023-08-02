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
