# Interactions Between the Vultron Protocol and SSVC

{% include-markdown "../includes/not_normative.md" %}

In the context of the Vultron Protocol, once a report has been validated
(i.e., it is in the RM [*Valid*](../topics/process_models/rm/index.md#the-valid-v-state) state, $q^{rm} \in V$), it must be prioritized to
determine what further effort, if any, is necessary.
While any prioritization scheme might be used, here we demonstrate an application of the [SSVC](https://github.com/CERTCC/SSVC){:target="_blank"} model.

{== TODO merge with SSVC section of [Situation Awareness](../topics/other_uses/situation_awareness.md) ==}

## SSVC Supplier and Deployer Trees

The default outcomes for both the SSVC [*Supplier*](https://github.com/CERTCC/SSVC/blob/v2.1/doc/graphics/ssvc_2_supplier.pdf){:target="_blank"}
and [*Deployer*](https://github.com/CERTCC/SSVC/blob/v2.1/doc/graphics/ssvc_2_deployer_SeEUMss.pdf){:target="_blank"} Trees are
*Defer*, *Scheduled*, *Out of Cycle*, and *Immediate*.
The mapping from SSVC outcomes to RM states is straightforward, as shown below for the *Supplier Tree* and
the *Deployer Tree*.

!!! note "SSVC *Supplier Tree* Mapping to RM States"

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

!!! note "SSVC *Deployer Tree* Mapping to RM States"

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

The
SSVC *Defer*
output maps directly onto the RM [*Deferred*](../topics/process_models/rm/index.md#the-deferred-d-state) state.
Otherwise, the three outputs that imply further action is necessary&mdash;Scheduled_,
*Out-of-Cycle*, and *Immediate*&mdash;all proceed to the RM [*Accepted*](../topics/process_models/rm/index.md#the-accepted-a-state) state.
The different categories imply different processes within the *Accepted* state.
But because the RM model does not dictate internal organizational processes, further description of what those processes
might look like is out of scope for this crosswalk.

We remind readers of a key takeaway from the protocol requirements in
the main part of this documentation:

!!! note ""

    Vendors SHOULD communicate their prioritization choices when making
    either a _defer_ ($\{V,A\} \xrightarrow{d} D$) or _accept_
    ($\{V,D\} \xrightarrow{a} A$) transition out of the _Valid_,
    _Deferred_, or _Accepted_ states.

## SSVC Coordinator Trees

SSVC version 2 offers two decision trees for Coordinators: A [*Coordinator Triage Tree*](https://github.com/CERTCC/SSVC/blob/v2.1/doc/graphics/ssvc_2_coord-triage.pdf){:target="_blank"}
and a [*Coordinator Publish Tree*](https://github.com/CERTCC/SSVC/blob/v2.1/doc/graphics/ssvc_2_coord-publish.pdf){:target="_blank"}.
The outputs for the *Coordinator Triage* Decision Tree are *Decline*, *Track*, and *Coordinate*.
Similar to the *Supplier Tree* mapping above, the mapping here is simple, as shown below.

!!! note "SSVC *Coordinator Triage Tree* Mapped to RM States"

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

Again, whereas the *Decline* output maps directly to the RM [*Deferred*](../topics/process_models/rm/index.md#the-deferred-d-state) state, the remaining two
states (*Track* and *Coordinate*) imply the necessity for distinct processes within the Coordinator's RM [*Accepted*](../topics/process_models/rm/index.md#the-accepted-a-state) state.

On the other hand, the SSVC *Coordinator Publish Tree* falls entirely within the Coordinator's *Accepted* state, so its
output does not directly induce any Coordinator RM state transitions.
However, a number of its decision points *do* touch on the protocol models, which we cover next.

## SSVC Decision Points and the Vultron Protocol

Additional connections between the protocol and the SSVC decision trees are possible.
We now examine how individual SSVC tree decision points can inform or be informed by Participant states in the
Vultron Protocol.

### Exploitation

The SSVC *Exploitation* decision point permits three possible values:

- *None*
- *PoC*
- *Active*

These values map directly onto state subsets in the [Case State (CS) model](../topics/process_models/cs/index.md), as shown below.

!!! note "SSVC *Exploitation* Decision Point Mapped to CS States"

    $$ SSVC(exploitation) =
    \begin{cases}
        None & \iff q^{cs} \in \cdot\cdot\cdot\cdot xa \\
        PoC & \iff  q^{cs} \in \cdot\cdot\cdot\cdot Xa \\
        Active & \iff q^{cs} \in \cdot\cdot\cdot\cdot\cdot A \\
    \end{cases}$$

A value of *None* implies that no exploits have been made public, and no attacks have been observed
(i.e., $q^{cs} \in \cdot\cdot\cdot\cdot xa$).
The *PoC* value means that an exploit is public, but no attacks have been observed
(i.e., $q^{cs} \in \cdot\cdot\cdot\cdot Xa$).
Finally, the *Active* value indicates attacks are occurring
(i.e., $q^{cs} \in \cdot\cdot\cdot\cdot\cdot A$).
These case states and SSVC values are equivalent in both directions, hence our use of the "if-and-only-if" ($\iff$) symbol.

### Report Public

The SSVC *Report Public* decision point also maps directly onto the [CS model](../topics/process_models/cs/index.md).
A value of *Yes* means that the report is public, equivalent to $q^{cs} \in \cdot\cdot\cdot P \cdot\cdot$.
On the other hand, a *No* value is the same as $q^{cs} \in \cdot\cdot\cdot p \cdot\cdot$.
As above, "$\iff$" indicates the bidirectional equivalence.

!!! note "SSVC *Report Public* Decision Point Mapped to CS States"

    $$SSVC(report~public) = 
    \begin{cases}
        Yes & \iff q^{cs} \in \cdot\cdot\cdot P \cdot\cdot \\
        No & \iff q^{cs} \in \cdot\cdot\cdot p \cdot\cdot \\
    \end{cases}$$

### Supplier Contacted

If the Supplier (Vendor) has been notified (i.e., there is reason to believe they are at least in the RM [*Received*](../topics/process_models/rm/index.md#the-received-r-state)
state, equivalent to the $V\cdot\cdot\cdot\cdot\cdot$ CS state subset) the *Supplier Contacted* value should be *Yes*,
otherwise it should be *No*.

!!! note "SSVC *Supplier Contacted* Decision Point Mapped to RM States"

    $$
    SSVC(supp.~contacted) = 
    \begin{cases}
        Yes & \iff q^{rm}_{Vendor} \not \in S \text{ or } q^{cs}_{Vendor} \in V\cdot\cdot\cdot\cdot\cdot \\
        \\
        No & \iff q^{rm}_{Vendor} \in S \text{ or } q^{cs}_{Vendor} \in vfd \cdot\cdot\cdot \\
    \end{cases}
    $$

### Report Credibility

Unlike most of the other SSVC decision points covered here that form a part of a Participant's report prioritization
process *after* report validation, the *Report Credibility* decision point forms an important step in the Coordinator's
validation process.
In fact, it is often the only validation step possible when the Coordinator lacks the ability to reproduce a
vulnerability whether due to constraints of resources, time, or skill.
Thus, a value of *Credible* can be expected to lead to an RM transition to [*Valid*](../topics/process_models/rm/index.md#the-valid-v-state) ($q^{rm} \in R \xrightarrow{v} V$),
assuming any additional validation checks also pass.
On the contrary, *Not-Credible* always implies the RM transition to [*Invalid*](../topics/process_models/rm/index.md#the-invalid-i-state) ($q^{rm} \in R \xrightarrow{i} I$)
because "Valid-but-not-Credible" is a contradiction.

!!! note "SSVC *Report Credibility* Decision Point Mapped to RM States"

    $$
    SSVC(report~cred.) = 
    \begin{cases}
        Credible & \text{implies }q^{rm} \xrightarrow{v} V \textrm{ (if validation also passes)}\\
        Not~Credible & \text{implies } q^{rm} \xrightarrow{i} I \\
    \end{cases}
    $$

### Public Value Added

The SSVC *Public Value Added* decision point can take on the values *Precedence*, *Ampliative*, or *Limited*.
*Precedence* means that publication adds value by providing information that is not widely known.
*Ampliative* means that publication might providing additional information or reach to information that may or may not
already be public.
*Limited* means that publication impact might be limited because the information is already widely known.

!!! note "SSVC *Public Value Added Decision Point Mapped to CS States"

        $$ SSVC(pva) = 
        \begin{cases}
            Precedence & \iff q^{cs} \in \cdot\cdot\cdot p\cdot\cdot \\
            Ampliative & \iff q^{cs} \in VFdp\cdot\cdot \textrm{ or } q^{cs} \in \cdot\cdot dP\cdot\cdot \\
            Limited & \iff q^{cs} \in VF\cdot P\cdot \\
        \end{cases}$$

### Supplier Engagement

The possible values for the *Supplier* (Vendor) *Engagement* decision point are *Active* or *Unresponsive*.
From the Coordinator's perspective, if enough Suppliers in a CVD case have communicated their engagement in a case
(i.e., enough Vendors are in the RM *Accepted* state already or are expected to make it there soon from either the
*Received* or *Valid* states), then the SSVC value would be *Active*.

Vendors in *Invalid* or *Closed* can be taken as disengaged, and it might be appropriate to select *Unresponsive* for
the SSVC *Engagement* decision point.

Vendors in either *Received* or *Deferred* might be either *Active* or *Unresponsive*, depending on the specific report
history.

This mapping is formalized below and in the figure that follows.

!!! note "SSVC *Supplier Engagement* Decision Point Mapped to RM States"

    $$ SSVC(supp.~eng.) = 
    \begin{cases}
        Active & \text{if } q^{rm} \in \{A,V\} \\
        \\
        \begin{cases}
            Active \\
            Unresponsive
        \end{cases} & \text{if } q^{rm} \in \{R,D\} \\
        \\
        Unresponsive & \text{if } q^{rm} \in \{I,C,S\} \\
    \end{cases}$$

```mermaid
---
title: "RM States and SSVC Supplier Engagement"
---
graph LR
    subgraph ssvc_se[SSVC Supplier Engagement]
        Active
        Unresponsive
    end
    subgraph rm_states[RM States]
        S[Start]
        R[Received]
        I[Invalid]
        V[Valid]
        D[Deferred]
        A[Accepted]
        C[Closed]
    end
    A --> Active
    V --> Active
    R --> Active
    D --> Active
    R--> Unresponsive
    D --> Unresponsive
    I --> Unresponsive
    C --> Unresponsive
    S --> Unresponsive
```

### Supplier Involvement

The *Supplier Involvement* decision point can take on the values *Fix-Ready*, *Cooperative*, or *Uncooperative/Unresponsive*.
We begin by noting the equivalence of the *Fix-Ready* value with the similarly named substate of the CS model.

!!! note "SSVC *Supplier Involvement* Decision Point Mapped to CS States"

    $$\begin{aligned}
    \label{eq:ssvc_supplier_involvement_fr}
        SSVC(supp.~inv.) = Fix~Ready \iff q^{cs} \in VF \cdot\cdot\cdot\cdot
    \end{aligned}$$

The Vendor RM states map onto these values as formalized below and shown in the figure below.

!!! note "SSVC Supplier Involvement Decision Point Mapped to Vendor RM States"

    $$\begin{aligned}
    \label{eq:ssvc_supplier_involvement}
    SSVC(supp.~inv.) = 
    \begin{cases}
        \begin{cases}
            Fix~Ready \\
            Cooperative
        \end{cases} & \text{if } q^{rm} \in A \\
        \\
        Cooperative & \text{if } q^{rm} \in V \\
        \\
        Uncoop./Unresp. & \text{if } q^{rm} \in \{R,I,D,C,S\} \\
    \end{cases}
    \end{aligned}$$

```mermaid
---
title: "RM States and SSVC Supplier Involvement"
---
graph LR
    subgraph rm_states[RM States]
        S[Start]
        R[Received]
        I[Invalid]
        V[Valid]
        D[Deferred]
        A[Accepted]
        C[Closed]
    end

    subgraph ssvc_si[SSVC Supplier Involvement]
        fr[Fix-Ready]
        co[Cooperative]
        un[Uncooperative/Unresponsive]
    end
    A --> fr
    A --> co
    V --> co
    R --> un
    D --> un
    I --> un
    C --> un
    S --> un
```

!!! tip "*Engagement* vs. *Involvement*: What's the Difference?"

    Note the discrepancy between the mappings given for SSVC _Supplier Engagement_ versus those for _Supplier Involvement_.
    This distinction is most prominent in the connections from the _Received_ and _Deferred_ RM states in the two figures above.
    These differences are the result of the relative timing of the two different decisions they support within a CVD case.

    The decision to Coordinate (i.e., whether the Coordinator should move from RM _Valid_ to RM _Accept_ 
    ($q^{rm} \in V \xrightarrow{a} A$) occurs early in the Coordinator's RM process.
    The SSVC _Supplier Engagement_ decision point is an attempt to capture this information.
    This early in the process, allowances must be made for Vendors who may not have completed their own validation or 
    prioritization processes. 
    Hence, the mapping allows Vendors in any valid yet unclosed state ($q^{rm} \in \{R,V,A,D\}$) to be categorized as 
    _Active_ for this decision point.


    On the other hand, the decision to Publish&mdash;a choice that falls entirely within the Coordinator's RM _Accepted_ 
    state&mdash;occurs later, at which time, more is known about each Vendor's level of involvement in the case
    to that point. 
    By the time the publication decision is made, the Vendor(s) have had ample opportunity to engage in the CVD process.
    They might already have a _Fix-Ready_ ($q^{cs} \in VF \cdot\cdot\cdot\cdot$), or they might be working toward it
    (i.e., SSVC _Cooperative_).
    However, if the Coordinator has reached the point where they are making a publication decision, and the Vendor has 
    yet to actively engage in the case for whatever reason&mdash;as indicated by their failure to reach the RM 
    _Accepted_ state or demonstrate progress toward it by at least getting to RM _Valid_ 
    ($q^{rm} \in \{A,V\}$)&mdash;then they can be categorized as _Uncooperative/Unresponsive_.

!!! example "SSVC Decision Points and Anticipated Transitions"

    Other SSVC decision points may be informative about which transitions to
    expect in a case. Two examples apply here:
    
    1. *Supplier Engagement*
    acts to gauge the likelihood of the **F** transitions.
    Coordination becomes more necessary the lower that likelihood is.
    2. *Utility* (the usefulness of the exploit to the adversary) acts
    to gauge the likelihood of the **A** transition.
