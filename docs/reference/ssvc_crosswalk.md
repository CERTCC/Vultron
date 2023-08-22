# Interactions Between the MPCVD Protocol and SSVC {#app:ssvc_mpcvd_protocol}

Once a report has been validated (i.e., it is in the
[RM]{acronym-label="RM" acronym-form="singular+short"} $Valid$ state,
$q^{rm} \in V$), it must be prioritized to determine what further
effort, if any, is necessary. While any prioritization scheme might be
used, in this appendix, we apply the [SSVC]{acronym-label="SSVC"
acronym-form="singular+full"} model.

## SSVC Supplier and Deployer Trees {#sec:ssvc_supplier}

The default outcomes for both the [SSVC]{acronym-label="SSVC"
acronym-form="singular+short"} Supplier and Deployer Trees are $Defer$,
$Scheduled$, $Out~of~Cycle$, and $Immediate$. The mapping from
[SSVC]{acronym-label="SSVC" acronym-form="singular+short"} outcomes to
[RM]{acronym-label="RM" acronym-form="singular+short"} states is
straightforward, as shown in
[\[eq:ssvc_supplier_tree_output\]](#eq:ssvc_supplier_tree_output){reference-type="eqref"
reference="eq:ssvc_supplier_tree_output"} for the Supplier Tree and
[\[eq:ssvc_deployer_tree_output\]](#eq:ssvc_deployer_tree_output){reference-type="eqref"
reference="eq:ssvc_deployer_tree_output"} for the Deployer Tree. The
[SSVC]{acronym-label="SSVC" acronym-form="singular+short"} $Defer$
output maps directly onto the [RM]{acronym-label="RM"
acronym-form="singular+short"} $Deferred$ state. Otherwise, the three
outputs that imply further action is necessary---$Scheduled$,
$Out~of~Cycle$, and $Immediate$---all proceed to the
[RM]{acronym-label="RM" acronym-form="singular+short"} $Accepted$ state.
The different categories imply different processes within the $Accepted$
state. But because the [RM]{acronym-label="RM"
acronym-form="singular+short"} model does not dictate internal
organizational processes, further description of what those processes
might look like is out of scope for this report.

$$\label{eq:ssvc_supplier_tree_output}
    q^{rm} \in
    \begin{cases}
        \xrightarrow{d} D & \text{when } SSVC(Supplier~Tree) = Defer \\
        \\
        \xrightarrow{a} A & \text{when } SSVC(Supplier~Tree) \in  
        \begin{Bmatrix}
            Scheduled \\
            Out~of~Cycle \\
            Immediate \\
        \end{Bmatrix} \\
    \end{cases}$$

$$\label{eq:ssvc_deployer_tree_output}
    q^{rm} \in
    \begin{cases}
        \xrightarrow{d} D & \text{when } SSVC(Deployer~Tree) = Defer \\
        \\
        \xrightarrow{a} A & \text{when } SSVC(Deployer~Tree) \in  
        \begin{Bmatrix}
            Scheduled \\
            Out~of~Cycle \\
            Immediate \\
        \end{Bmatrix} \\
    \end{cases}$$

We remind readers of a key takeaway from the protocol requirements in
the main part of this report:

-   Vendors SHOULD communicate their prioritization choices when making
    either a $defer$ ($\{V,A\} \xrightarrow{d} D$) or $accept$
    ($\{V,D\} \xrightarrow{a} A$) transition out of the $Valid$,
    $Deferred$, or $Accepted$ states.

## SSVC Coordinator Trees {#sec:ssvc_coordinator}

[SSVC]{acronym-label="SSVC" acronym-form="singular+short"} version 2
offers two decision trees for Coordinators: A Coordinator Triage Tree
and a Coordinator Publish Tree. The outputs for the Coordinator Triage
Decision Tree are $Decline$, $Track$, and $Coordinate$. Similar to the
Supplier Tree mapping in §[1.1](#sec:ssvc_supplier){reference-type="ref"
reference="sec:ssvc_supplier"}, the mapping here is simple, as shown in
[\[eq:ssvc_coordinator_triage_tree_output\]](#eq:ssvc_coordinator_triage_tree_output){reference-type="eqref"
reference="eq:ssvc_coordinator_triage_tree_output"}. Again, whereas the
$Decline$ output maps directly to the [RM]{acronym-label="RM"
acronym-form="singular+short"} $Deferred$ state, the remaining two
states ($Track$ and $Coordinate$) imply the necessity for distinct
processes within the Coordinator's [RM]{acronym-label="RM"
acronym-form="singular+short"} $Accepted$ state.

$$\label{eq:ssvc_coordinator_triage_tree_output}
q^{rm} \in
\begin{cases}
    \xrightarrow{d} D & \text{when } SSVC(Coord.~Triage~Tree) = Decline \\
    \\
    \xrightarrow{a} A & \text{when } SSVC(Coord.~Triage~Tree) \in  
    \begin{Bmatrix}
        Track \\
        Coordinate \\
    \end{Bmatrix} \\
\end{cases}$$

On the other hand, the [SSVC]{acronym-label="SSVC"
acronym-form="singular+short"} Coordinator Publish tree falls entirely
within the Coordinator's $Accepted$ state, so its output does not
directly induce any Coordinator [RM]{acronym-label="RM"
acronym-form="singular+short"} state transitions. However, a number of
its decision points *do* touch on the protocol models, which we cover in
§[1.3](#sec:ssvc_decision_points){reference-type="ref"
reference="sec:ssvc_decision_points"}.

## SSVC Decision Points and the MPCVD Protocol {#sec:ssvc_decision_points}

Additional connections between the protocol and the
[SSVC]{acronym-label="SSVC" acronym-form="singular+short"} decision
trees are possible. We now examine how individual
[SSVC]{acronym-label="SSVC" acronym-form="singular+short"} tree decision
points can inform or be informed by Participant states in the
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} protocol.

### Exploitation

The SSVC Exploitation decision point permits three possible values:
$None$, $PoC$, and $Active$. These values map directly onto state
subsets in the [CS]{acronym-label="CS" acronym-form="singular+short"}
model, as shown in
[\[eq:ssvc_exploitation_cs_states\]](#eq:ssvc_exploitation_cs_states){reference-type="eqref"
reference="eq:ssvc_exploitation_cs_states"}. A value of $None$ implies
that no exploits have been made public, and no attacks have been
observed (i.e., $q^{cs} \in \wc\wc\wc\wc xa$). The $PoC$ value means
that an exploit is public, but no attacks have been observed (i.e.,
$q^{cs} \in \wc\wc\wc\wc Xa$). Finally, the $Active$ value indicates
attacks are occurring (i.e., $q^{cs} \in \wc\wc\wc\wc\wc A$). These case
states and SSVC values are equivalent in both directions, hence our use
of the "if-and-only-if" ($\iff$) symbol.

$$\label{eq:ssvc_exploitation_cs_states}
    SSVC(exploitation) =
    \begin{cases}
        None & \iff q^{cs} \in \wc\wc\wc\wc xa \\
        PoC & \iff  q^{cs} \in \wc\wc\wc\wc Xa \\
        Active & \iff q^{cs} \in \wc\wc\wc\wc\wc A \\
    \end{cases}$$

### Report Public

The SSVC Report Public decision point also maps directly onto the
[CS]{acronym-label="CS" acronym-form="singular+short"} model. A value of
$Yes$ means that the report is public, equivalent to
$q^{cs} \in \wc\wc\wc P \wc\wc$. On the other hand, a $No$ value is the
same as $q^{cs} \in \wc\wc\wc p \wc\wc$. As above, "$\iff$" indicates
the bidirectional equivalence.

$$SSVC(report~public) = 
    \begin{cases}
        Yes & \iff q^{cs} \in \wc\wc\wc P \wc\wc \\
        No & \iff q^{cs} \in \wc\wc\wc p \wc\wc \\
    \end{cases}$$

### Supplier Contacted

If the Supplier (Vendor) has been notified (i.e., there is reason to
believe they are at least in the [RM]{acronym-label="RM"
acronym-form="singular+short"} $Received$ state, equivalent to the
$V\wc\wc\wc\wc\wc$ [CS]{acronym-label="CS"
acronym-form="singular+short"} state subset) the Supplier Contacted
value should be $Yes$, otherwise it should be $No$.

$$SSVC(supp.~contacted) = 
    \begin{cases}
        Yes & \text{if } q^{rm}_{Vendor} \not \in S \text{ or } q^{cs}_{Vendor} \in V\wc\wc\wc\wc\wc \\
        \\
        No & \text{if $q^{rm}_{Vendor} \in S$ or $q^{cs}_{Vendor} \in vfd \wc\wc\wc$} \\
    \end{cases}$$

### Report Credibility

Unlike most of the other [SSVC]{acronym-label="SSVC"
acronym-form="singular+short"} decision points covered here that form a
part of a Participant's report prioritization process *after* report
validation, the Report Credibility decision point forms an important
step in the Coordinator's validation process. In fact, it is often the
only validation step possible when the Coordinator lacks the ability to
reproduce a vulnerability whether due to constraints of resources, time,
or skill. Thus, a value of $Credible$ can be expected to lead to an
[RM]{acronym-label="RM" acronym-form="singular+short"} transition to
$Valid$ ($q^{rm} \in R \xrightarrow{v} V$), assuming any additional
validation checks also pass. On the contrary, $Not~Credible$ always
implies the [RM]{acronym-label="RM" acronym-form="singular+short"}
transition to $Invalid$ ($q^{rm} \in R \xrightarrow{i} I$) because
"Valid-but-not-Credible" is a contradiction.

$$SSVC(report~cred.) = 
    \begin{cases}
        Credible & \text{implies $q^{rm} \xrightarrow{v} V$ \small(if validation also passes)}\\
        Not~Credible & \text{implies } q^{rm} \xrightarrow{i} I \\
    \end{cases}$$

### Supplier Engagement

The possible values for the Supplier (Vendor) Engagement decision point
are $Active$ or $Unresponsive$. From the Coordinator's perspective, if
enough Suppliers in a [CVD]{acronym-label="CVD"
acronym-form="singular+short"} case have communicated their engagement
in a case (i.e., enough Vendors are in the [RM]{acronym-label="RM"
acronym-form="singular+short"} $Accepted$ state already or are expected
to make it there soon from either the $Received$ or $Valid$ states),
then the [SSVC]{acronym-label="SSVC" acronym-form="singular+short"}
value would be $Active$.

Vendors in $Invalid$ or $Closed$ can be taken as disengaged, and it
might be appropriate to select $Unresponsive$ for the
[SSVC]{acronym-label="SSVC" acronym-form="singular+short"} Engagement
decision point.

Vendors in either $Received$ or $Deferred$ might be either $Active$ or
$Unresponsive$, depending on the specific report history.

This mapping is shown in
[\[eq:ssvc_supplier_engagement\]](#eq:ssvc_supplier_engagement){reference-type="eqref"
reference="eq:ssvc_supplier_engagement"} and on the left side of Figure
[\[fig:rm_ssvc_coord_map\]](#fig:rm_ssvc_coord_map){reference-type="ref"
reference="fig:rm_ssvc_coord_map"}.

$$\label{eq:ssvc_supplier_engagement}
SSVC(supp.~eng.) = 
\begin{cases}
    Active & \text{if } q^{rm} \in \{A,V\} \\
    \\
    \begin{rcases}
        Active \\
        Unresponsive
    \end{rcases} & \text{if } q^{rm} \in \{R,D\} \\
    \\
    Unresponsive & \text{if } q^{rm} \in \{I,C,S\} \\
\end{cases}$$

### Supplier Involvement

The Supplier Involvement decision point can take on the values
$Fix~Ready$, $Cooperative$, or $Uncooperative/Unresponsive$. We begin by
noting the equivalence of the $Fix~Ready$ value with the similarly named
substate of the [CS]{acronym-label="CS" acronym-form="singular+short"}
model.

$$\begin{aligned}
\label{eq:ssvc_supplier_involvement_fr}
    SSVC(supp.~inv.) = Fix~Ready \iff q^{cs} \in VF \wc\wc\wc\wc
\end{aligned}$$

The Vendor [RM]{acronym-label="RM" acronym-form="singular+short"} states
map onto these values as shown in
[\[eq:ssvc_supplier_involvement\]](#eq:ssvc_supplier_involvement){reference-type="eqref"
reference="eq:ssvc_supplier_involvement"} and on the right side of
Figure
[\[fig:rm_ssvc_coord_map\]](#fig:rm_ssvc_coord_map){reference-type="ref"
reference="fig:rm_ssvc_coord_map"}.

$$\begin{aligned}
\label{eq:ssvc_supplier_involvement}
SSVC(supp.~inv.) = 
\begin{cases}
    \begin{rcases}
        Fix~Ready \\
        Cooperative
    \end{rcases} & \text{if } q^{rm} \in A \\
    \\
    Cooperative & \text{if } q^{rm} \in V \\
    \\
    Uncoop./Unresp. & \text{if } q^{rm} \in \{R,I,D,C,S\} \\
\end{cases}
\end{aligned}$$

### Engagement vs. Involvement: What's the Difference?

Note the discrepancy between the mappings given for
[SSVC]{acronym-label="SSVC" acronym-form="singular+short"} Supplier
Engagement versus those for Supplier Involvement. This distinction is
most prominent in the connections from the $R$ and $D$
[RM]{acronym-label="RM" acronym-form="singular+short"} states on the
left and right sides of Figure
[\[fig:rm_ssvc_coord_map\]](#fig:rm_ssvc_coord_map){reference-type="ref"
reference="fig:rm_ssvc_coord_map"}. These differences are the result of
the relative timing of the two different decisions they support within
case.

The decision to Coordinate (i.e., whether the Coordinator should move
from [RM]{acronym-label="RM" acronym-form="singular+short"} $Valid$ to
[RM]{acronym-label="RM" acronym-form="singular+short"} $Accept$
($q^{rm} \in V \xrightarrow{a} A$)) occurs early in the Coordinator's
[RM]{acronym-label="RM" acronym-form="singular+short"} process. The
[SSVC]{acronym-label="SSVC" acronym-form="singular+short"} Supplier
Engagement decision point is an attempt to capture this information.
This early in the process, allowances must be made for Vendors who may
not have completed their own validation or prioritization processes.
Hence, the mapping allows Vendors in any valid yet unclosed state
($q^{rm} \in \{R,V,A,D\}$) to be categorized as Active for this decision
point.

On the other hand, the decision to Publish---a choice that falls
entirely within the Coordinator's [RM]{acronym-label="RM"
acronym-form="singular+short"} $Accepted$ state---occurs later, at which
time, more is known about each Vendor's level of involvement in the case
to that point. By the time the publication decision is made, the
Vendor(s) have had ample opportunity to engage in the
[CVD]{acronym-label="CVD" acronym-form="singular+short"} process. They
might already have a $Fix~Ready$ ($q^{cs} \in VF \wc\wc\wc\wc$), or they
might be working toward it (i.e., [SSVC]{acronym-label="SSVC"
acronym-form="singular+short"} $Cooperative$). However, if the
Coordinator has reached the point where they are making a publication
decision, and the Vendor has yet to actively engage in the case for
whatever reason---as indicated by their failure to reach the
[RM]{acronym-label="RM" acronym-form="singular+short"} $Accepted$ state
or demonstrate progress toward it by at least getting to
[RM]{acronym-label="RM" acronym-form="singular+short"} $Valid$
($q^{rm} \in \{A,V\}$)---then they can be categorized as
$Uncooperative/Unresponsive$.
