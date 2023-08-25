# CVD Case State Model

{% include-markdown "../../../includes/normative.md" %}

Here we complete the definition of the CVD Case State (CS) model begun in the [previous page](index.md).
As a reminder, this model provides a high-level view of the state of a CVD case and is 
derived from [A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=735513).

---

{% include-markdown "../dfa_notation_definition.md" %}

As in the [RM](../rm/index.md) and [EM](../em/index.md) process models, we wish to define a 5-tuple
$(\mathcal{Q},\Sigma,\delta,q_0,F)$, this time for the CS model.


In the CS model, a state $q^{cs}$ represents the status of each of the six [substates](index.md).
State labels use the substate notation at left.
For example, the state _VFdpXa_ represents Vendor is aware, fix is ready, fix not deployed, no public awareness, exploit
is public, and no attacks.
The order in which the events occurred does not matter when defining the state.
However, we will observe a notation convention keeping the letter names in the same case-insensitive order
$(v,f,d,p,x,a)$.

The Case State model builds upon the CVD substates defined in the [previous page](index.md), summarized
in the table below.

<a name="cs-model-states-defined"></a>
{% include-markdown "cs_substates_table.md" %}

???+ note inline end "Vendor Fix Path Formalism"

    $$D \implies F \implies V$$

CS states can be any combination of statuses, provided that a number of caveats elaborated in
[CS Transitions](#cs-transitions) are met. 
One such caveat worth noting here is that valid states must follow what we call the *Vendor fix path*.


The reason is causal: For a fix to be deployed (_D_), it must have been ready (_F_) for deployment.
And for it to be ready, the Vendor must have already known (_V_) about the vulnerability. 
As a result, valid states must begin with one of the following strings: _vfd_, _Vfd_, _VFd_, or _VFD_.

!!! tip inline end "See also"

    See §2.4 of [A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=735513)
    for an expanded explanation of the *Vendor fix path*.


```mermaid
---
title: Vendor Fix Path
---
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

???+ note inline end "CS Model Start and End States ($q^{cs}_0$ and $\mathcal{F}^{cs}$) Defined"

    $$q^{cs}_0 = vfdpxa$$

    $$\mathcal{F}^{cs} = \{ VFDPXA \}$$

## CS Start and End States

All vulnerability cases start in the base state _vfdpxa_ in which no
events have occurred.

The lone final state in which all events have occurred is _VFDPXA_.  


!!! tip "The Map is not the Territory"

    Note that this is a place where our
    model of the vulnerability lifecycle diverges from what we expect to
    observe in CVD
    cases in the real world. There is ample evidence that most
    vulnerabilities never have exploits published or attacks observed.
    See for example:
    
    - [Historical Analysis of Exploit Availability Timelines](https://www.usenix.org/conference/cset20/presentation/householder)
    - [Exploit Prediction Scoring System (EPSS)](https://dl.acm.org/doi/pdf/10.1145/3436242)
    
    Therefore, practically speaking, we might expect vulnerabilities to wind up in one of
    
    $$\mathcal{F}^\prime = \{ {VFDPxa}, {VFDPxA}, {VFDPXa}, {VFDPXA} \}$$ 
    
    at the time a report is closed (i.e., when $q^{rm} \xrightarrow{c} C$). In
    fact, most count a CVD as successful when reports are closed in
    $q^{cs} \in VFDPxa$ because it means that the defenders won the race
    against adversaries. The distinction between the [RM](../rm/index.md) and CS processes is important; Participants can
    close cases whenever their [RM](../rm/index.md) process dictates, independent of the
    CS state. In other
    words, it remains possible for exploits to be published or attacks to be
    observed long after the [RM](../rm/index.md) process has closed a case.

!!! info "CS Model Wildcard Notation"
    
    We frequently need to refer to subsets of $\mathcal{Q}^{cs}$. To do so,
    we will use a dot ($\cdot$) to represent a single character wildcard.
    For example, $VFdP\cdot\cdotrefers to the subset of $\mathcal{Q}^{cs}$ in
    which the Vendor is aware, a fix is ready but not yet deployed, and the
    public is aware of the vulnerability, yet we are indifferent to whether
    exploit code has been made public or attacks have been observed.
    Specifically,

    $${VFdP\cdot\cdot} = \{{VFdPxa}, {VFdPxA}, {VFdPXa}, {VFdPXA}\} \subset{\mathcal{Q}}^{cs}$$

## CS Transitions

In this section, we elaborate on the input symbols and transition functions for our CS DFA.
A row-wise reading of the [CVD Case Substates](#cs-model-states-defined) table above
implies a set of events corresponding to each specific substate change, which we correspond to the symbols in the DFA.

| Symbol | Description |                                      Formalism                                       |
|:------:| :--- |:------------------------------------------------------------------------------------:|
| **V**  | A Vendor becomes aware of a vulnerability |           $vfd\cdot\cdot\cdot \xrightarrow{\mathbf{V}} Vfd\cdot\cdot\cdot$           |
| **F**  | A Vendor readies a fix for a vulnerability |           $Vfd\cdot\cdot\cdot \xrightarrow{\mathbf{F}} VFd\cdot\cdot\cdot$           |
| **D**  | A Deployer deploys a fix for a vulnerability |           $VFd\cdot\cdot\cdot \xrightarrow{\mathbf{D}} VFD\cdot\cdot\cdot$           |
| **P**  | Information about a vulnerability becomes known to the public | $\cdot\cdot\cdot p \cdot\cdot \xrightarrow{\mathbf{P}} \cdot\cdot\cdot P \cdot\cdot$ |
| **X**  | An exploit for a vulnerability is made public | $\cdot\cdot\cdot\cdot x \cdot \xrightarrow{\mathbf{X}} \cdot\cdot\cdot\cdot X \cdot$ |
| **A**  | Attacks exploiting a vulnerability are observed |  $\cdot\cdot\cdot\cdot\cdot a \xrightarrow{\mathbf{A}} \cdot\cdot\cdot\cdot\cdot A$  |


???+ note inline end "CS Model Input Symbols ($\Sigma^{cs}$) Defined"

    $$\Sigma^{cs} = \{\mathbf{V},\mathbf{F},\mathbf{D},\mathbf{P},\mathbf{X},\mathbf{A}\}$$

    Here we diverge somewhat from the notation used for the
    [RM](../rm/index.md) and [EM](../em/index.md) models, which use lowercase letters for transitions and
    uppercase letters for states. Because CS state names already use both lowercase
    and uppercase letters, here we use a bold font for the symbols of the
    CS DFA to differentiate the transition from the corresponding substate it leads
    to: e.g., $vfd\cdot\cdot\cdot \xrightarrow{\mathbf{V}} Vfd\cdot\cdot\cdot$.

We define the set of symbols for our CS DFA as $\Sigma^{cs}$ at right.


For the CS model, an input symbol $\sigma^{cs} \in \Sigma^{cs}$ is "read" when a Participant
observes a change in status (a Vendor is notified and exploit code has
been published, etc.). For the sake of simplicity, we begin with the
assumption that observations are globally known---that is, a status
change observed by any CVD Participant is known to all. In the real
world, we believe the [Formal Vultron MPCVD Protocol](../../../reference/formal_protocol/index.md)
is poised to ensure eventual
consistency with this assumption through the communication of perceived
case state across coordinating parties.

### CS Transitions Defined 

Here we define the allowable transitions between states in the
CS model.
Transitions in the CS model follow a few rules described in
detail in §2.4 of [A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=735513) which we summarize here:

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
    is a causal requirement as outlined in [substates](cs_model.md).

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
    therefore, $v\cdot\cdot P \cdot\cdot$ can only lead to $V\cdot\cdot P \cdot\cdot$.

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
    pX: ...pX.
    PX: ...PX.
    pX --> PX
```

Therefore, for all practical purposes, we can simplify the full $pxa \rightarrow PXA$ diagram:


{% include-markdown "pxa_diagram.md" %}

down to the following: 

{% include-markdown "pxa_diagram_simple.md" %}


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
does seem plausible that the likelihood of **P** occurring
increases when attacks are occurring. 

???+ note "Formalism"

    The probability of public awareness given attacks observed is
    greater than the probability of public awareness without attacks.

    $$
    P(\mathbf{P} \mid \cdot\cdot\cdot p \cdot A) > P(\mathbf{P} \mid \cdot\cdot\cdot p \cdot a)
    $$

Logically, this is a result of there being more ways for the public to discover the vulnerability when attacks are 
happening than when they are not:

- For states in $\cdot\cdot\cdot p \cdot a$, public awareness depends on the normal vulnerability discovery and reporting
process.
- States in $\cdot\cdot\cdot p \cdot A$ include that possibility and add the potential for discovery as a result of
security incident analysis.

Hence,

!!! note ""

    Once attacks have been observed, fix development SHOULD accelerate,
    the embargo teardown process SHOULD begin, and publication and
    deployment SHOULD follow as soon as is practical.


## A Regular Grammar for the CS model

Following the complete state machine diagram in above, we can summarize the transition functions of the CS model as a
right-linear grammar $\delta^{cs}$.

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

!!! tip "For more information"

    A more thorough examination of the strings generated by this grammar,
    their interpretation as the possible histories of all CVD cases, and implications for measuring the efficacy of the 
    overall CVD process writ large can be found in [A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=735513).

## CS Model Diagram

A diagram of the CS process, including its states and transitions, is shown below.

{% include-markdown "vfdpxa_diagram.md" %}


## CS Model Fully Defined

In combination, the full definition of the Case State DFA $(\mathcal{Q},q_0,\mathcal{F},\Sigma,\delta)^{cs}$ is shown 
below.

???+ note "Case State Model $(\mathcal{Q},q_0,\mathcal{F},\Sigma,\delta)^{cs}$ Fully Defined"

    $$CS = 
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
                            \end{Bmatrix},  \\
                    q^{cs}_0 = & vfdpxa,  \\
                    \mathcal{F}^{cs} = &\{VFDPXA\},  \\
                    \Sigma^{cs} = & \{\mathbf{V},\mathbf{F},\mathbf{D},\mathbf{P},\mathbf{X},\mathbf{A}\}, \\
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
                \end{aligned}
        \end{pmatrix}$$

