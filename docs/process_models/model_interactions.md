# Model Interactions {#ch:interactions}

Here we reflect on the interactions between the
RM,
EM, and
CS models within the
overall MPCVD
process.

## Interactions Between the RM and EM Models {#sec:rm_em_interactions}

There are additional constraints on how the RM and EM processes interact.

##### Start Embargo Negotiations As Early as Possible

-   The EM process
    MAY begin (i.e., the initial $propose$ transition
    $q^{em} \in N \xrightarrow{p} P$) prior to the report being sent to
    a potential Participant ($q^{rm} \in S$), for example, when a
    Participant wishes to ensure acceptable embargo terms prior to
    sharing a report with a potential recipient.

-   If it has not already begun, the EM process SHOULD begin when a recipient
    is in RM $Received$ ($q^{rm} \in R$) whenever possible.

##### Negotiate Embargoes for Active Reports

-   Embargo Management MAY begin in any of the active RM states
    ($q^{rm} \in \{ R,V,A \}$).

-   Embargo Management SHOULD NOT begin in an inactive RM state
    ($q^{rm} \in \{ I,D,C \}$).

##### Negotiate Embargoes Through Validation and Prioritization

-   Embargo Management MAY run in parallel to validation
    ($q^{rm} \in \{R,I\} \xrightarrow{\{v,i\}} \{V,I\}$) and
    prioritization ($q^{rm} \in V \xrightarrow{\{a,d\}} \{A,D\}$)
    activities.

##### Renegotiate Embargoes While Reports Are Valid Yet Unclosed

-   EM revision proposals ($q^{em} \in A \xrightarrow{p} R$) and
    acceptance or rejection of those proposals
    (${q^{em} \in R \xrightarrow{\{a,r\}} A}$) MAY occur during any of
    the valid yet unclosed RM states (${q_{rm} \in \{ V,A,D \} }$).

##### Avoid Embargoes for Invalid Reports...

-   Embargo Management SHOULD NOT begin with a proposal from a
    Participant in RM $Invalid$ ($q^{rm} \in I$).

##### ...but Don't Lose Momentum if Validation Is Pending

-   Outstanding embargo negotiations
    ($q^{em} \in P \xrightarrow{\{r,p\}} \{N,P\}$) MAY continue in
    RM $Invalid$
    ($q^{rm} \in I$) (e.g., if it is anticipated that additional
    information may be forthcoming to promote the report from $Invalid$
    to $Valid$) ($q^{rm} \in I \xrightarrow{v} V$).

##### Only Accept Embargoes for Possibly Valid Yet Unclosed Reports

-   Embargo Management MAY proceed from EM $Proposed$ to EM $Accepted$
    ($q^{em} \in P \xrightarrow{a} A$) when RM is neither $Invalid$ nor $Closed$
    ($q^{rm} \in \{R,V,A,D\}$).

-   Embargo Management SHOULD NOT proceed from EM $Proposed$ to EM $Accepted$ when
    RM is $Invalid$
    or $Closed$ ($q^{rm} \in \{I,C\}$).

-   Embargo Management MAY proceed from EM $Proposed$ to EM $None$
    ($q^{em} \in P \xrightarrow{r} N$) when RM is $Invalid$ or $Closed$.

##### Report Closure, Deferral, and Active Embargoes

-   Participants SHOULD NOT close reports
    ($q^{rm} \in \{I,D,A\} \xrightarrow{c} C$) while an embargo is
    active ($q^{em} \in \{ A,R \}$).

-   Instead, reports with no further tasks SHOULD be held in either
    $Deferred$ or $Invalid$ (${q^{rm} \in \{ D,I\}}$) (depending on the
    report validity status) until the embargo has terminated
    (${q^{em} \in X}$). This allows Participants to stop work on a
    report but still maintain their participation in an extant embargo.

-   Notwithstanding, Participants who choose to close a report
    ($q^{rm} \in \{I,D,A\} \xrightarrow{c} C$) while an embargo remains
    in force ($q^{em} \in \{A,R\}$) SHOULD communicate their intent to
    either continue to adhere to the embargo or terminate their
    compliance with it.

```{=html}
<!-- -->
```
-   Report closure or deferral does not terminate an embargo. A
    Participant's closure or deferral ($q^{rm} \in \{C,D\}$) of a report
    while an embargo remains active ($q^{em} \in \{A,R\}$) and while
    other Participants remain engaged ($q^{rm} \in \{R,V,A\}$) SHALL NOT
    automatically terminate the embargo.

-   Any changes to a Participant's intention to adhere to an active
    embargo SHOULD be communicated clearly in addition to any necessary
    notifications regarding RM or EM state changes.

## RM - CVD and EM - CVD Model Interactions {#sec:rm_cvd}

The RM and
EM models interact
with the CS model
described in Chapter [\[sec:model\]](#sec:model){reference-type="ref"
reference="sec:model"}. Here we will review the constraints arising from
the interaction of the RM and EM models with each of the
CS transition events
represented by its symbols. As a reminder, the CS transition symbols ($\Sigma^{cs}$) from
the Householder and Spring 2021 report [@householder2021state] are
represented as bold capital letters.
$$\Sigma^{cs} = \{ \mathbf{V},~\mathbf{F},~\mathbf{D},~\mathbf{P},~\mathbf{X},~\mathbf{A} \} 
    \tag{\ref{eq:events} revisited}$$

##### Global vs. Participant-Specific Aspects of the CS Model.

The CS model
encompasses both Participant-specific and global aspects of a
CVD case. In
particular, the Vendor fix path substates---Vendor unaware ($vfd$),
Vendor aware ($Vfd$), fix ready ($VFd$), and fix deployed ($VFD$)---are
specific to each Vendor Participant in a case. On the other hand, the
remaining substates represent global facts about the case
status---public awareness ($p,P$), exploit public ($x,X$), and attacks
observed ($a,A$). This local versus global distinction will become
important in Chapter
[\[sec:formal_protocol\]](#sec:formal_protocol){reference-type="ref"
reference="sec:formal_protocol"}.

### Vendor Notification

Vendor Awareness ($\mathbf{V}$) occurs when a Participant---typically a
Finder, Coordinator, or another Vendor---is in RM $Accepted$ and notifies the Vendor
($q^{cs} \in vfd\wc\wc\wc \xrightarrow{\mathbf{V}} Vfd\wc\wc\wc$). In
turn, the Vendor starts in $q^{rm} = Received$ and proceeds to follow
their validation and prioritization routines. We previously outlined
this in Table
[\[tab:participant_rm_actions\]](#tab:participant_rm_actions){reference-type="ref"
reference="tab:participant_rm_actions"}.

Depending on which parties are involved in a CVD case, the EM process might already be underway prior
to Vendor notification (e.g., $q^{em} \in \{P,A,R\}$). For example, a
Reporter and Coordinator might have already agreed to a disclosure
timeline. Or, in an MPCVD case, other Vendors may have already been
coordinating the case under an embargo and only recently realized the
need to engage with a new Vendor on the case. The latter example is
consistent with public narratives about the Meltdown/Spectre
vulnerabilities [@wright2018meltdown].

Once a case has reached $q^{cs} \in Vfdpxa$ for at least one Vendor,

-   If the EM
    process has not started, it SHOULD begin as soon as possible.

-   Any proposed embargo SHOULD be decided ($accept$, $reject$) soon
    after the first Vendor is notified.

$$q^{cs} \in Vfdpxa \implies q^{em} \in
    \begin{cases}
        None \xrightarrow{propose} Proposed \\
        Proposed \begin{cases}
            \xrightarrow{reject} None \\
            \xrightarrow{accept} Accepted \\
        \end{cases} \\
        Accepted \\
        Revise \\
    \end{cases}$$

### Fix Ready {#sec:cs_f_em}

Fix Readiness ($\mathbf{F}$) can occur only when a Vendor is in the
$Accepted$ state. As a reminder, in MPCVD cases, each affected Vendor has their own
RM state, so this
constraint applies to each Vendor individually.

With respect to EM,
when the case state is $q^{cs} \in VF\wc pxa$, it's usually too late to
start a new embargo. Once a case has reached $q^{cs} \in VF\wc pxa$,

-   New embargo negotiations SHOULD NOT start.

-   Proposed but not-yet-agreed-to embargoes SHOULD be rejected.

-   Existing embargoes ($q^{em} \in \{Active,~Revise\}$) MAY continue
    but SHOULD prepare to $terminate$ soon.

$$q^{cs} \in VF\wc pxa \implies q^{em} \in
    \begin{cases}
        None \\
        Proposed \xrightarrow{reject} None \\
        Accepted \\
        Revise \\
    \end{cases}$$

In MPCVD cases,
where some Vendors are likely to reach $q^{cs} \in VF\wc\wc\wc\wc$
before others,

-   Participants MAY propose an embargo extension to allow trailing
    Vendors to catch up before publication.

-   Participants SHOULD accept reasonable extension proposals for such
    purposes when possible (e.g., when other constraints could still be
    met by the extended deadline).

### Fix Deployed

For vulnerabilities in systems where the Vendor controls deployment, the
Fix Deployment ($\mathbf{D}$) event can only occur if the Vendor is in
$q^{rm} = Accepted$.

For vulnerabilities in systems where Public Awareness must precede
Deployment ($\mathbf{P} \prec \mathbf{D}$), the Vendor status at the
time of deployment might be irrelevant---assuming, of course, that they
at least passed through $q^{rm} = Accepted$ at some point as is required
for Fix Ready ($\mathbf{F}$), which, in turn, is a prerequisite for
deployment ($\mathbf{D}$).

As regards EM, by
the time a fix has been deployed ($q^{cs} \in VFD\wc\wc\wc$),

-   New embargoes SHOULD NOT be sought.

-   Any existing embargo SHOULD terminate.

$$q^{cs} \in {VFD} \wc\wc\wc \implies q^{em} \in
    \begin{cases}
        None \\
        Proposed \xrightarrow{reject} None \\
        Accepted \xrightarrow{terminate} eXited \\
        Revise \xrightarrow{terminate} eXited \\
    \end{cases}$$

As with the *Fix Ready* scenario in
§[1.2.2](#sec:cs_f_em){reference-type="ref" reference="sec:cs_f_em"},
MPCVD cases may
have Vendors in varying states of *Fix Deployment*. Therefore the
embargo extension caveats from that section apply to the *Fix Deployed*
state as well.

### Public Awareness

Within the context of a coordinated publication process, ($\mathbf{P}$)
requires at least one Participant to be in the $q^{rm} = Accepted$ state
because Participants are presumed to publish only on cases they have
accepted. Ideally, the Vendor is among those Participants, but as
outlined in the *CERT Guide to Coordinated Vulnerability Disclosure*
[@householder2017cert], that is not strictly necessary.

That said, the publishing party might be outside of *any* existing
coordination process. For example, this is the situation when a report
is already in the midst of a CVD process and a party outside the
CVD case reveals
the vulnerability publicly (e.g., parallel discovery, embargo leaks).

As for EM, the whole
point of an embargo is to prevent $\mathbf{P}$ from occurring until
other objectives (e.g., $q^{cs} \in VF\wc px \wc$) have been met.
Therefore, once $\mathbf{P}$ has happened and the case state reaches
$q^{cs} \in \wc\wc\wc P \wc\wc$,

-   New embargoes SHALL NOT be sought.

-   Any existing embargo SHALL terminate.

$$q^{cs} \in \wc\wc\wc P \wc\wc \implies q^{em} \in
    \begin{cases}
        None \\
        Proposed \xrightarrow{reject} None \\
        Accepted \xrightarrow{terminate} eXited \\
        Revise \xrightarrow{terminate} eXited \\
    \end{cases}$$

### Exploit Public

Exploit publishers may also be presumed to have a similar
RM state model for
their own work. Therefore, we can expect them to be in an
RM $Accepted$ state
at the time of exploit code publication ($\mathbf{X}$). However, we
cannot presume that those who publish exploit code will be Participants
in a pre-public CVD
process. That said,

-   Exploit Publishers who *are* Participants in pre-public
    CVD cases
    ($q^{cs} \in \wc\wc\wc p \wc\wc$) SHOULD comply with the protocol
    described here, especially when they also fulfill other roles (e.g.,
    Finder, Reporter, Coordinator, Vendor) in the process.

For example, as described in the Householder and Spring 2021 report
[@householder2021state], the preference for
$\mathbf{P} \prec \mathbf{X}$ dictates that

-   Exploit publishers SHOULD NOT release exploit code while an embargo
    is active ($q^{em} \in \{A,R\}$).

In the Householder and Spring 2021 report [@householder2021state], the
authors argue that public exploit code is either preceded by Public
Awareness ($\mathbf{P}$) or immediately leads to it. Therefore, once
$\mathbf{X}$ has occurred ($q^{cs} \in \wc\wc\wc\wc X \wc$),

-   New embargoes SHALL NOT be sought.

-   Any existing embargo SHALL terminate.

$$q^{cs} \in \wc\wc\wc\wc X \wc \implies q^{em} \in
    \begin{cases}
        None \\
        Proposed \xrightarrow{reject} None \\
        Accepted \xrightarrow{terminate} eXited \\
        Revise \xrightarrow{terminate} eXited \\
    \end{cases}$$

### Attacks Observed

Nothing in this or any other CVD process model should be interpreted as
constraining adversary activity.

-   Participants MUST treat attacks as an event that could occur at any
    time and adapt their process as needed in light of the available
    information.

As we outlined in
§[\[sec:early_termination\]](#sec:early_termination){reference-type="ref"
reference="sec:early_termination"}, when attacks are occurring,
embargoes can often be of more benefit to adversaries than defenders.
However, we also acknowledged in
§[\[sec:transition_function\]](#sec:transition_function){reference-type="ref"
reference="sec:transition_function"} that narrowly scoped attacks need
not imply widespread adversary knowledge of the vulnerability. In such
scenarios, it is possible that early embargo termination---leading to
publication---might be of more assistance to other adversaries than it
is to defenders. Thus, we need to allow room for Participant judgment
based on their case-specific situation awareness.

Formally, once attacks have been observed
($q^{cs} \in \wc\wc\wc\wc\wc \mathbf{A}$),

-   New embargoes SHALL NOT be sought.

-   Any existing embargo SHOULD terminate.

$$q^{cs} \in \wc\wc\wc\wc\wc A \implies q^{em} \in
    \begin{cases}
        None \\
        Proposed \xrightarrow{reject} None \\
        Accepted \xrightarrow{terminate} eXited \\
        Revise \xrightarrow{terminate} eXited \\
    \end{cases}$$
