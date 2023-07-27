# CVD Case State Model {#sec:model}

!!! note "TODO"
    - [ ] regex replace acronym pointers with the acronym
    - [ ] replace first use of an acronym on a page with its expansion (if not already done)
    - [ ] OR replace acronym usage with link to where it's defined
    - [ ] reproduce diagrams using mermaid
    - [ ] replace text about figures to reflect mermaid diagrams
    - [ ] replace latex tables with markdown tables
    - [ ] replace some equations with diagrams (especially for equations describing state changes)
    - [ ] move latex math definitions into note blocks `???+ note _title_` to offset from text
    - [ ] move MUST SHOULD MAY etc statements into note blocks with empty title `!!! note ""` to offset from text
    - [ ] revise cross-references to be links to appropriate files/sections
    - [ ] replace latex citations with markdown citations (not sure how to do this yet)
    - [ ] review text for flow and readability as a web page
    - [ ] add section headings as needed for visual distinction
    - [ ] add links to other sections as needed
    - [ ] add links to external resources as needed
    - [ ] replace phrases like `this report` or `this section` with `this page` or similar
    - [ ] add `above` or `below` for in-page cross-references if appropriate (or just link to the section)
    - [ ] reduce formality of language as needed
    - [ ] move diagrams to separate files and `include-markdown` them

In this chapter, we revisit the CS model from the Householder and Spring 2021
report [@householder2021state]. A complete derivation of the
CS model can be
found in that report. Here, we are primarily interested in the final
model, which comprises 32 states and their transitions.

As in the previous two chapters, we wish to define 5-tuple
$(\mathcal{Q},\Sigma,\delta,q_0,F)$ [@kandar2013automata], this time for
the CS model.
However, due to the size of the final CS model, we begin with some necessary
background on the substates of the model in
§[1.1](#sec:cvd_case_states){reference-type="ref"
reference="sec:cvd_case_states"} prior to defining the Case States in
§[1.2](#sec:cs_substates_to_states){reference-type="ref"
reference="sec:cs_substates_to_states"}.

## CVD Case Substates {#sec:cvd_case_states}

In our model, the state of the world is a specification of the current
status of all the events in the vulnerability lifecycle model described
in the Householder and Spring 2021 report [@householder2021state]. We
describe the relevant factors as substates below. For notational
purposes, each substate status is represented by a letter for that part
of the state of the world. For example, _v_ means no Vendor awareness
and _V_ means the Vendor is aware. The complete set of status labels is
shown in
Table [\[tab:event_status\]](#tab:event_status){reference-type="ref"
reference="tab:event_status"}.

### The _Vendor Awareness_ Substate (_v_, _V_)

The *Vendor Awareness* substate corresponds to *Disclosure* in the
Arbaugh, Fithen, and McHugh article, "Windows of Vulnerability: A Case
Study analysis" [@arbaugh2000windows] and *vulnerability discovered by
Vendor* in Bilge and Dumitraş's article, "Before we knew it: an
empirical study of zero-day attacks in the real
world" [@bilge2012before]. In the interest of model simplicity, we are
not concerned with *how* the Vendor finds out about the vulnerability's
existence---whether it was found via internal testing, reported within a
CVD process, or
noticed as the result of incident or malware analysis.

```mermaid
stateDiagram-v2
    direction LR
    v : Vendor Unaware (v)
    V : Vendor Aware (V)
    v --> V : vendor becomes aware
```

### The _Fix Readiness_ Substate (_f_, _F_)
 
The *Fix Readiness* substate refers to the Vendor's creation and
possession of a fix that *could* be deployed to a vulnerable system *if*
the system owner knew of its existence. Here we differ somewhat from
previous
models [@arbaugh2000windows; @frei2010modeling; @bilge2012before]; their
models address the *release* of the fix rather than its *readiness* for
release. This distinction is necessary because we are interested in
modeling the activities and states leading up to disclosure. Fix
*release* is a goal of the CVD process, whereas fix *readiness* is a
significant process milestone along the way.

```mermaid
stateDiagram-v2
    direction LR
    f : Fix Not Ready (f)
    F : Fix Ready (F)
    f --> F : fix is ready
```

### The _Fix Deployed_ Substate (_d_, _D_) 

The *Fix Deployed* substate reflects the deployment status of an
existing fix. The model in the Householder and Spring 2021 report
[@householder2021state] was initially designed to treat this substate as
a singular binary state for a case, but we intend to relax that here to
reflect a more realistic perspective in which each Deployer maintains
their own instance of this state value. It remains a binary state for
each Deployer, which, however, is still a simplification.

```mermaid
stateDiagram-v2
    direction LR
    d : Fix Not Deployed (d)
    D : Fix Deployed (D)
    d --> D : fix is deployed
```


### The _Public Awareness_ Substate (_p_, _P_) 

The *Public Awareness* substate corresponds to *Publication* in the
Arbaugh, Fithen, and McHugh article  [@arbaugh2000windows], *time of
public disclosure* in Frei et al.'s article Modeling the Security
Ecosystem---The Dynamics of (In)Security  [@frei2010modeling]; and
*vulnerability disclosed publicly* in Bilge and Dumitraş's article
 [@bilge2012before]. The public might find out about a vulnerability
through the Vendor's announcement of a fix, a news report about a
security breach, a conference presentation by a researcher, or a variety
of other means. As above, we are primarily concerned with the occurrence
of the event itself rather than the details of *how* the public
awareness event arises.

```mermaid
stateDiagram-v2
    direction LR
    p : Public Unaware (p)
    P : Public Aware (P)
    p --> P : public becomes aware
```

### The _Exploit Public_ Substate (_x_, _X_) 

The *Exploit Public* substate reflects whether the method of exploiting
a vulnerability has been made public in sufficient detail to be
reproduced by others. Posting PoC code to a widely available site or
including the exploit code in a commonly available exploit tool meets
this criteria; privately held exploits do not.

```mermaid
stateDiagram-v2
    direction LR
    x : Exploit Not Public (x)
    X : Exploit Public (X)
    x --> X : exploit is public
```

### The _Attacks Observed_ Substate (_a_, _A_) 

The *Attacks Observed* substate reflects whether attacks have been
observed in which the vulnerability was exploited. This substate
requires evidence that the vulnerability was exploited; we can then
presume the existence of exploit code regardless of its availability to
the public. Analysis of malware from an incident might meet
_Attacks Observed_ but not _Exploit Public_, depending on how closely
the attacker holds the malware. Use of a public exploit in an attack
meets both _Exploit Public_ and _Attacks Observed_.

```mermaid
stateDiagram-v2
    direction LR
    a : Attacks Not Observed (a)
    A : Attacks Observed (A)
    a --> A : attacks are observed
```

### CS Model Design Choices

We chose to include the *Fix Ready*, *Fix Deployed*, and *Public
Awareness* events so that our model could better accommodate two common
modes of modern software deployment:

-   *shrinkwrap* is a traditional distribution mode where the Vendor and
    Deployer are distinct entities, and Deployers must be made aware of
    the fix before it can be deployed. In this case, both *Fix Ready*
    and *Public Awareness* are necessary for *Fix Deployment* to occur.

-   *SAAS* is a
    more recent delivery mode where the Vendor also plays the role of
    Deployer. In this distribution mode, *Fix Ready* can lead directly
    to *Fix Deployed* with no dependency on *Public Awareness*.

We note that so-called *silent fixes* by Vendors can sometimes result in
a fix being deployed without public awareness even if the Vendor is not
the Deployer. Thus, it is possible (but unlikely) for *Fix Deployed* to
occur before *Public Awareness* even in the shrinkwrap mode above. It is
also possible, and somewhat more likely, for *Public Awareness* to occur
before *Fix Deployed* in the SAAS mode as well.

## CVD Case States {#sec:cs_substates_to_states}

In the CS model, a
state $q^{cs}$ represents the status of each of the six substates. State
labels inherit the substate notation from above: lowercase letters
designate events that have not occurred, and uppercase letters designate
events that have occurred in a particular state. For example, the state
_VFdpXa_ represents Vendor is aware, fix is ready, fix not deployed, no
public awareness, exploit is public, and no attacks. The order in which
the events occurred does not matter when defining the state. However, we
will observe a notation convention keeping the letter names in the same
case-insensitive order $(v,f,d,p,x,a)$.

???+ note inline end "Vendor Fix Path Formalism"

    

    $$D \implies F \implies V$$

CS states can be any
combination of statuses, provided that a number of caveats elaborated in
§[1.3](#sec:transitions){reference-type="ref"
reference="sec:transitions"} are met. One such caveat worth noting here
is that valid states must follow what we call the *Vendor fix path*.[^1]
The reason is causal: For a fix to be deployed (_D_), it must have been
ready (_F_) for deployment. And for it to be ready, the Vendor must have
already known (_V_) about the vulnerability. As a result, valid states must begin with one
of the following strings: _vfd_, _Vfd_, _VFd_, or _VFD_.

```mermaid
stateDiagram-v2
    vfd : Vendor is unaware (vfd)
    Vfd : Vendor is aware (Vfd)
    VFd : Vendor is aware and fix is ready (VFd)
    VFD : Vendor is aware and fix is deployed (VFD)
    vfd --> Vfd : vendor becomes aware
    Vfd --> VFd : fix is ready
    VFd --> VFD : fix is deployed
```


The CS model is thus
composed of 32 possible states, which we define as $\mathcal{Q}^{cs}$.

???+ note "CS Model States ($\mathcal{Q}^{cs}$) Defined"

    $$
    \mathcal{Q}^{cs} = 
    \begin{Bmatrix}
        vfdpxa, & vfdPxa, & vfdpXa, & vfdPXa, \\
        vfdpxA, & vfdPxA, & vfdpXA, & vfdPXA, \\
        Vfdpxa, & VfdPxa, & VfdpXa, & VfdPXa, \\
        VfdpxA, & VfdPxA, & VfdpXA, & VfdPXA, \\
        VFdpxa, & VFdPxa, & VFdpXa, & VFdPXa, \\
        VFdpxA, & VFdPxA, & VFdpXA, & VFdPXA, \\
        VFDpxa, & VFDPxa, & VFDpXa, & VFDPXa, \\
        VFDpxA, & VFDPxA, & VFDpXA, & VFDPXA
    \end{Bmatrix}$$

### CS Start and End States

???+ note inline end "CS Model Start and End States ($q^{cs}_0$ and $\mathcal{F}^{cs}$) Defined"

    $$q^{cs}_0 = vfdpxa$$

    $$\mathcal{F}^{cs} = \{ VFDPXA \}$$

All vulnerabilities start in the base state _vfdpxa_ in which no
events have occurred.  The lone final state in which all events have
occurred is _VFDPXA_.  

#### The Map is not the Territory

Note that this is a place where our
model of the vulnerability lifecycle diverges from what we expect to
observe in CVD
cases in the real world. There is ample evidence that most
vulnerabilities never have exploits published or attacks observed
[@householder2020historical; @jacobs2021exploit]. Therefore, practically
speaking, we might expect vulnerabilities to wind up in one of

$$\mathcal{F}^\prime = \{ {VFDPxa}, {VFDPxA}, {VFDPXa}, {VFDPXA} \}$$ 

at the time a report is closed (i.e., when $q^{rm} \xrightarrow{c} C$). In
fact, most count a CVD as successful when reports are closed in
$q^{cs} \in VFDPxa$ because it means that the defenders won the race
against adversaries. The distinction between the [RM](../rm) and CS processes is important; Participants can
close cases whenever their [RM](../rm) process dictates, independent of the
CS state. In other
words, it remains possible for exploits to be published or attacks to be
observed long after the [RM](../rm) process has closed a case.

!!! info "CS Model Wildcard Notation"
    
    We frequently need to refer to subsets of $\mathcal{Q}^{cs}$. To do so,
    we will use a dot ($\cdot$) to represent a single character wildcard.
    For example, $VFdP\cdot\cdot$ refers to the subset of $\mathcal{Q}^{cs}$ in
    which the Vendor is aware, a fix is ready but not yet deployed, and the
    public is aware of the vulnerability, yet we are indifferent to whether
    exploit code has been made public or attacks have been observed.
    Specifically,

    $${VFdP\cdot\cdot} = \{{VFdPxa}, {VFdPxA}, {VFdPXa}, {VFdPXA}\} \subset{\mathcal{Q}}^{cs}$$

## CS Transitions {#sec:transitions}

In this section, we elaborate on the input symbols and transition
functions for our CS
DFA. A row-wise
reading of {== Table
[\[tab:event_status\]](#tab:event_status){reference-type="ref"
reference="tab:event_status"} ==} implies a set of events corresponding to
each specific substate change, which we correspond to the symbols in the
CS
DFA.

-   $\mathbf{V}$ -- A Vendor becomes aware of a vulnerability
    $vfd\cdot\cdot\cdot \to Vfd\cdot\cdot\cdot$

-   $\mathbf{F}$ -- A Vendor readies a fix for a vulnerability
    $Vfd\cdot\cdot\cdot \to VFd\cdot\cdot\cdot$

-   $\mathbf{D}$ -- A Deployer deploys a fix for a vulnerability
    $VFd\cdot\cdot\cdot \to VFD\cdot\cdot\cdot$

-   $\mathbf{P}$ -- Information about a vulnerability becomes known to
    the public $\cdot\cdot\cdot p\cdot\cdot \to \cdot\cdot\cdot P\cdot\cdot$

-   $\mathbf{X}$ -- An exploit for a vulnerability is made public
    $\cdot\cdot\cdot\cdot x\cdot \to \cdot\cdot\cdot\cdot X\cdot$

-   $\mathbf{A}$ -- Attacks exploiting a vulnerability are observed
    $\cdot\cdot\cdot\cdot\cdot a \to \cdot\cdot\cdot\cdot\cdot A$


???+ note inline end "CS Model Input Symbols ($\Sigma^{cs}$) Defined"

    $$\label{eq:events}
        \Sigma^{cs} = \{\mathbf{V},\mathbf{F},\mathbf{D},\mathbf{P},\mathbf{X},\mathbf{A}\}$$

We define the set of symbols for our CS DFA as $\Sigma^{cs}$:

Here we diverge somewhat from the notation used for the
[RM](../rm) and [EM](../em) models described
in previous chapters, which use lowercase letters for transitions and
uppercase letters for states. Because CS state names already use both lowercase
and uppercase letters, here we use a bold font for the symbols of the
CS
DFA to
differentiate the transition from the corresponding substate it leads
to: e.g., $vfd\cdot\cdot\cdot \xrightarrow{\mathbf{V}} Vfd\cdot\cdot\cdot$.

For the CS model, an
input symbol $\sigma^{cs} \in \Sigma^{cs}$ is "read" when a Participant
observes a change in status (a Vendor is notified and exploit code has
been published, etc.). For the sake of simplicity, we begin with the
assumption that observations are globally known---that is, a status
change observed by any CVD Participant is known to all. In the real
world, we believe the [Formal Vultron MPCVD Protocol](../../formal_protocol)
is poised to ensure eventual
consistency with this assumption through the communication of perceived
case state across coordinating parties.

### CS Transitions Defined {#sec:transition_function}

Here we define the allowable transitions between states in the
CS model. A diagram
of the CS process,
including its states and transitions, is shown in Figure
[\[fig:vfdpxa_map\]](#fig:vfdpxa_map){reference-type="ref"
reference="fig:vfdpxa_map"}.

Transitions in the CS model follow a few rules described in
detail in §2.4 of the Householder and Spring 2021
report [@householder2021state], which we summarize here:

-   Because states correspond to the status of events that have or have
    not occurred, and all state transitions are irreversible (i.e., we
    assume history is immutable), the result will be an acyclic directed
    graph of states beginning at $q^{cs}_0={vfdpxa}$ and ending at
    $\mathcal{F}^{cs}=\{VFDPXA\}$ with allowed transitions as the edges.
    In practical terms for the CS model, this means there is an arrow
    of time from _vfdpxa_ through _VFDPXA_ in which each individual
    state transition changes exactly one letter from lowercase to
    uppercase.

-   The *Vendor fix path*
    ($vfd \cdot\cdot\cdot \xrightarrow{\mathbf{V}} Vfd \cdot\cdot\cdot \xrightarrow{\mathbf{F}} VFd \cdot\cdot\cdot \xrightarrow{\mathbf{D}} VFD \cdot\cdot\cdot$)
    is a causal requirement as outlined in
    §[1.2](#sec:cs_substates_to_states){reference-type="ref"
    reference="sec:cs_substates_to_states"}.

```mermaid
stateDiagram-v2
    direction LR
    vfd: vfd...
    Vfd: Vfd...
    VFd: VFd...
    VFD: VFD...
    
    [*] --> vfd
    vfd --> Vfd
    Vfd --> VFd
    VFd --> VFD
    VFD --> [*]
```


-   Vendors are presumed to know at least as much as the public does;
    therefore, $v\cdot\cdot P\cdot\cdot$ can only lead to $V\cdot\cdot P\cdot\cdot$.

```mermaid
stateDiagram-v2
    direction LR
    vP: v..P..
    VP: V..P..
    vP --> VP
```


#### Exploit Publication Causes Public Awareness

Exploit publication is tantamount to public awareness; therefore,
$\cdot\cdot\cdot pX \cdot$ can only lead to $\cdot\cdot\cdot\cdot PX \cdot$.

```mermaid
stateDiagram-v2
    direction LR
    pX: ...pX..
    PX: ...PX..
    pX --> PX
```

Therfore, 
```mermaid
stateDiagram-v2
    direction LR
    [*] --> pxa

    pxa --> Pxa : P
    pxa --> pXa : X
    pxa --> pxA : A
    
    pXa --> PXa : P
    pXa --> pXA : A
    
    pxA --> PxA : P
    pxA --> pXA : X

    Pxa --> PxA : A
    Pxa --> PXa : X
    
    pXA --> PXA : P
    PXa --> PXA : A
    PxA --> PXA : X
    PXA --> [*]
```
simplifies to 

```mermaid
stateDiagram-v2
    direction LR
    [*] --> pxa
    
    pxa --> Pxa : P
    pxa --> PXa : X,P
    pxa --> pxA : A
    
   
    pxA --> PxA : P
    pxA --> PXA : X,P

    Pxa --> PxA : A
    Pxa --> PXa : X
    
    PXa --> PXA : A
    PxA --> PXA : X
    PXA --> [*]
```

#### Attacks Do Not Necessarily Cause Public Awareness

In this model, attacks observed when a vulnerability is unknown to the
public ($\cdot\cdot\cdot p \cdot A$) need not immediately cause public awareness
($\cdot\cdot\cdot P \cdot A$), although, obviously, that can and does happen.
Our reasoning for allowing states in $\cdot\cdot\cdot p \cdot A$ to persist is
twofold:

-   First, the connection between attacks and exploited vulnerabilities
    is often made later during incident analysis. While the attack
    itself may have been observed much earlier, the knowledge of *which*
    vulnerability it targeted may be delayed until after other events
    have occurred.

-   Second, attackers are not a monolithic group. An attack from a niche
    set of threat actors does not automatically mean that the knowledge
    and capability of exploiting a particular vulnerability is widely
    available to all possible adversaries. Publication, in that case,
    might assist other adversaries more than it helps defenders.

In other words, although $\cdot\cdot\cdot p \cdot A$ does not require an
immediate transition to $\cdot\cdot\cdot P \cdot A$ the way
$\cdot\cdot\cdot pX \cdot \xrightarrow{\mathbf{P}} \cdot\cdot\cdot PX \cdot$ does, it
does seem plausible that the likelihood of $\mathbf{P}$ occurring
increases when attacks are occurring. Logically, this is a result of
there being more ways for the public to discover the vulnerability when
attacks are happening than when they are not. For states in
$\cdot\cdot\cdot p \cdot a$, the public depends on the normal vulnerability
discovery and reporting process. States in $\cdot\cdot\cdot p \cdot A$ include
that possibility and add the potential for discovery as a result of
security incident analysis. Hence,

!!! note ""

    Once attacks have been observed, fix development SHOULD accelerate,
    the embargo teardown process SHOULD begin, and publication and
    deployment SHOULD follow as soon as is practical.





```mermaid
stateDiagram-v2
    [*] --> vfdpxa
    vfdpxa --> vfdPxa : P
    vfdpxa --> vfdPXa : X,P
    vfdpxa --> vfdpxA : A
    vfdpxA --> vfdPxA : P
    vfdpxA --> vfdPXA : X,P
 	vfdpxa --> Vfdpxa : V
	vfdpxA --> VfdpxA : V
	vfdPxa --> VfdPxa : V
	vfdPXa --> VfdPXa : V
	vfdPxA --> VfdPxA : V
	vfdPXA --> VfdPXA : V
    Vfdpxa --> VfdPxa : P
    Vfdpxa --> VfdPXa : X,P
    Vfdpxa --> VfdpxA : A
    VfdpxA --> VfdPxA : P
    VfdpxA --> VfdPXA : X,P
    VfdPxa --> VfdPxA : A
    VfdPxa --> VfdPXa : X
    VfdPXa --> VfdPXA : A
    VfdPxA --> VfdPXA : X
	Vfdpxa --> VFdpxa : F
	VfdpxA --> VFdpxA : F
	VfdPxa --> VFdPxa : F
	VfdPXa --> VFdPXa : F
	VfdPxA --> VFdPxA : F
	VfdPXA --> VFdPXA : F
    VFdpxa --> VFdPxa : P
    VFdpxa --> VFdPXa : X,P
    VFdpxa --> VFdpxA : A
    VFdpxA --> VFdPxA : P
    VFdpxA --> VFdPXA : X,P
    VFdPxa --> VFdPxA : A
    VFdPxa --> VFdPXa : X
    VFdPXa --> VFdPXA : A
    VFdPxA --> VFdPXA : X
	VFdpxa --> VFDpxa : D
	VFdpxA --> VFDpxA : D
	VFdPxa --> VFDPxa : D
	VFdPXa --> VFDPXa : D
	VFdPxA --> VFDPxA : D
	VFdPXA --> VFDPXA : D
    VFDpxa --> VFDPxa : P
    VFDpxa --> VFDPXa : X,P
    VFDpxa --> VFDpxA : A
    VFDpxA --> VFDPxA : P
    VFDpxA --> VFDPXA : X,P
    VFDPxa --> VFDPxA : A
    VFDPxa --> VFDPXa : X
    VFDPXa --> VFDPXA : A
    VFDPxA --> VFDPXA : X
    VFDPXA --> [*]
```

### A Regular Grammar for the CS model

Following the complete state machine diagram in Figure
[\[fig:vfdpxa_map\]](#fig:vfdpxa_map){reference-type="ref"
reference="fig:vfdpxa_map"}, we can summarize the transition functions
of the CS model as a
right-linear grammar $\delta^{cs}$:

???+ note "CS Transition Function ($\delta^{cs}$) Defined"

    $$  \delta^{cs} =
        \begin{cases}
            vfdpxa &\to \mathbf{V}~Vfdpxa~|~\mathbf{P}~vfdPxa~|~\mathbf{X}~vfdpXa~|~\mathbf{A}~vfdpxA \\
            vfdpxA &\to \mathbf{V}~VfdpxA~|~\mathbf{P}~vfdPxA~|~\mathbf{X}~vfdpXA \\
            vfdpXa &\to \mathbf{P}~vfdPXa \\
            vfdpXA &\to \mathbf{P}~vfdPXA \\
            vfdPxa &\to \mathbf{V}~VfdPxa \\
            vfdPxA &\to \mathbf{V}~VfdPxA \\ 
            vfdPXa &\to \mathbf{V}~VfdPXa \\
            vfdPXA &\to \mathbf{V}~VfdPXA \\
            Vfdpxa &\to \mathbf{F}~VFdpxa~|~\mathbf{P}~VfdPxa~|~\mathbf{X}~VfdpXa~|~\mathbf{A}~VfdpxA \\
            VfdpxA &\to \mathbf{F}~VFdpxA ~|~ \mathbf{P}~VfdPxA ~|~ \mathbf{X}~VfdpXA \\
            VfdpXa &\to \mathbf{P}~VfdPXa \\
            VfdpXA &\to \mathbf{P}~VfdPXA \\
            VfdPxa &\to \mathbf{F}~VFdPxa ~|~ \mathbf{X}~VfdPXa ~|~ \mathbf{A}~VfdPxA \\
            VfdPxA &\to \mathbf{F}~VFdPxA ~|~ \mathbf{X}~VfdPXA \\
            VfdPXa &\to \mathbf{F}~VFdPXa ~|~ \mathbf{A}~VfdPXA \\
            VfdPXA &\to \mathbf{F}~VFdPXA \\ 
            VFdpxa &\to \mathbf{D}~VFDpxa~|~\mathbf{P}~VFdPxa ~|~ \mathbf{X}~VFdpXa ~|~ \mathbf{A}~VFdpxA \\
            VFdpxA &\to \mathbf{D}~VFDpxA ~|~ \mathbf{P}~VFdPxA ~|~ \mathbf{X}~VFdpXA \\
            VFdpXa &\to \mathbf{P}~VFdPXa \\
            VFdpXA &\to \mathbf{P}~VFdPXA \\
            VFdPxa &\to \mathbf{D}~VFDPxa ~|~ \mathbf{X}~VFdPXa ~|~ \mathbf{A}~VFdPxA \\
            VFdPxA &\to \mathbf{D}~VFDPxA ~|~ \mathbf{X}~VFDPXA \\
            VFdPXa &\to \mathbf{D}~VFDPXa ~|~ \mathbf{A}~VFdPXA \\
            VFdPXA &\to \mathbf{D}~VFDPXA \\
            VFDpxa &\to \mathbf{P}~VFDPxa ~|~ \mathbf{X}~VFDpXa ~|~ \mathbf{A}~VFDpxA \\
            VFDpxA &\to \mathbf{P}~VFDPxA ~|~ \mathbf{X}~VFDpXA \\
            VFDpXa &\to \mathbf{P}~VFDPXa \\
            VFDpXA &\to \mathbf{P}~VFDPXA \\
            VFDPxa &\to \mathbf{X}~VFDPXa ~|~ \mathbf{A}~VFDPxA \\
            VFDPxA &\to \mathbf{X}~VFDPXA \\
            VFDPXa &\to \mathbf{A}~VFDPXA \\
            VFDPXA &\to \varepsilon \\
        \end{cases}$$

A more thorough examination of the strings generated by this grammar,
their interpretation as the possible histories of all
CVD cases, and
implications for measuring the efficacy of the overall
CVD process writ
large can be found in the Householder and Spring 2021
report [@householder2021state].

## CS Model Fully Defined

In combination, the full definition of the CS DFA
$(\mathcal{Q},q_0,\mathcal{F},\Sigma,\delta)^{cs}$ is given by equations
[\[eq:all_states\]](#eq:all_states){reference-type="eqref"
reference="eq:all_states"}, [\[eq:q_0\]](#eq:q_0){reference-type="eqref"
reference="eq:q_0"}, [\[eq:F\]](#eq:F){reference-type="eqref"
reference="eq:F"}, [\[eq:events\]](#eq:events){reference-type="eqref"
reference="eq:events"}, and
[\[eq:delta_cs\]](#eq:delta_cs){reference-type="eqref"
reference="eq:delta_cs"}. For convenience, we have assembled them into
[\[eq:vfdpxa_dfa\]](#eq:vfdpxa_dfa){reference-type="eqref"
reference="eq:vfdpxa_dfa"}.

$$\label{eq:vfdpxa_dfa}
    CS = 
    \begin{pmatrix}
            \begin{aligned}
                    \mathcal{Q}^{cs} = & 
                        \begin{Bmatrix}
                            vfdpxa, & vfdPxa, & vfdpXa, & vfdPXa, \\
                            vfdpxA, & vfdPxA, & vfdpXA, & vfdPXA, \\
                            Vfdpxa, & VfdPxa, & VfdpXa, & VfdPXa, \\
                            VfdpxA, & VfdPxA, & VfdpXA, & VfdPXA, \\
                            VFdpxa, & VFdPxa, & VFdpXa, & VFdPXa, \\
                            VFdpxA, & VFdPxA, & VFdpXA, & VFdPXA, \\
                            VFDpxa, & VFDPxa, & VFDpXa, & VFDPXa, \\
                            VFDpxA, & VFDPxA, & VFDpXA, & VFDPXA
                        \end{Bmatrix}, &\textrm{\small{\eqref{eq:all_states}}} \\
                q^{cs}_0 = & vfdpxa, &\textrm{\small{\eqref{eq:q_0}}} \\
                \mathcal{F}^{cs} = &\{VFDPXA\}, &\textrm{\small{\eqref{eq:F}}} \\
                \Sigma^{cs} = & \{\mathbf{V},\mathbf{F},\mathbf{D},\mathbf{P},\mathbf{X},\mathbf{A}\},&\textrm{\small{\eqref{eq:events}}} \\
                    \delta^{cs} = &
    \begin{cases}
        vfdpxa &\to \mathbf{V}~Vfdpxa~|~\mathbf{P}~vfdPxa~|~\mathbf{X}~vfdpXa~|~\mathbf{A}~vfdpxA \\
        vfdpxA &\to \mathbf{V}~VfdpxA~|~\mathbf{P}~vfdPxA~|~\mathbf{X}~vfdpXA \\
        vfdpXa &\to \mathbf{P}~vfdPXa \\
        vfdpXA &\to \mathbf{P}~vfdPXA \\
        vfdPxa &\to \mathbf{V}~VfdPxa \\
        vfdPxA &\to \mathbf{V}~VfdPxA \\ 
        vfdPXa &\to \mathbf{V}~VfdPXa \\
        vfdPXA &\to \mathbf{V}~VfdPXA \\
        Vfdpxa &\to \mathbf{F}~VFdpxa~|~\mathbf{P}~VfdPxa~|~\mathbf{X}~VfdpXa~|~\mathbf{A}~VfdpxA \\
        VfdpxA &\to \mathbf{F}~VFdpxA ~|~ \mathbf{P}~VfdPxA ~|~ \mathbf{X}~VfdpXA \\
        VfdpXa &\to \mathbf{P}~VfdPXa \\
        VfdpXA &\to \mathbf{P}~VfdPXA \\
        VfdPxa &\to \mathbf{F}~VFdPxa ~|~ \mathbf{X}~VfdPXa ~|~ \mathbf{A}~VfdPxA \\
        VfdPxA &\to \mathbf{F}~VFdPxA ~|~ \mathbf{X}~VfdPXA \\
        VfdPXa &\to \mathbf{F}~VFdPXa ~|~ \mathbf{A}~VfdPXA \\
        VfdPXA &\to \mathbf{F}~VFdPXA \\ 
        VFdpxa &\to \mathbf{D}~VFDpxa~|~\mathbf{P}~VFdPxa ~|~ \mathbf{X}~VFdpXa ~|~ \mathbf{A}~VFdpxA \\
        VFdpxA &\to \mathbf{D}~VFDpxA ~|~ \mathbf{P}~VFdPxA ~|~ \mathbf{X}~VFdpXA \\
        VFdpXa &\to \mathbf{P}~VFdPXa \\
        VFdpXA &\to \mathbf{P}~VFdPXA \\
        VFdPxa &\to \mathbf{D}~VFDPxa ~|~ \mathbf{X}~VFdPXa ~|~ \mathbf{A}~VFdPxA \\
        VFdPxA &\to \mathbf{D}~VFDPxA ~|~ \mathbf{X}~VFDPXA \\
        VFdPXa &\to \mathbf{D}~VFDPXa ~|~ \mathbf{A}~VFdPXA \\
        VFdPXA &\to \mathbf{D}~VFDPXA \\
        VFDpxa &\to \mathbf{P}~VFDPxa ~|~ \mathbf{X}~VFDpXa ~|~ \mathbf{A}~VFDpxA \\
        VFDpxA &\to \mathbf{P}~VFDPxA ~|~ \mathbf{X}~VFDpXA \\
        VFDpXa &\to \mathbf{P}~VFDPXa \\
        VFDpXA &\to \mathbf{P}~VFDPXA \\
        VFDPxa &\to \mathbf{X}~VFDPXa ~|~ \mathbf{A}~VFDPxA \\
        VFDPxA &\to \mathbf{X}~VFDPXA \\
        VFDPXa &\to \mathbf{A}~VFDPXA \\
        VFDPXA &\to \varepsilon \\
    \end{cases}
                    &\textrm{\small{\eqref{eq:delta_cs}}}
            \end{aligned}
    \end{pmatrix}$$

[^1]: See §2.4 of the Householder and Spring 2021 report
    [@householder2021state] for an expanded explanation of the *Vendor
    fix path*.
