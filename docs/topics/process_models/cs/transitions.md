# CS Transitions

{% include-markdown "../../../includes/normative.md" %}

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
been published, etc.).
For the sake of simplicity, we begin with the
assumption that observations are globally known&mdash;that is, a status
change observed by any CVD Participant is known to all. In the real
world, we believe the [Formal Vultron Protocol](../../../reference/formal_protocol/index.md)
is poised to ensure eventual
consistency with this assumption through the communication of perceived
case state across coordinating parties.

## CS Transitions Defined

Here we define the allowable transitions between states in the
CS model.
Transitions in the CS model follow a few rules described in
detail in §2.4 of [A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=735513) which we summarize here:

- Because states correspond to the status of events that have or have
    not occurred, and all state transitions are irreversible (i.e., we
    assume history is immutable), the result will be an acyclic directed
    graph of states beginning at $q^{cs}_0={vfdpxa}$ and ending at
    $\mathcal{F}^{cs}=\{VFDPXA\}$ with allowed transitions as the edges.
    In practical terms for the CS model, this means there is an arrow
    of time from *vfdpxa* through *VFDPXA* in which each individual
    state transition changes exactly one letter from lowercase to
    uppercase.

- The *Vendor fix path*
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

- Vendors are presumed to know at least as much as the public does;
    therefore, $v\cdot\cdot P \cdot\cdot$ can only lead to $V\cdot\cdot P \cdot\cdot$.

```mermaid
stateDiagram-v2
    direction LR
    vP: v..P..
    VP: V..P..
    vP --> VP
```

### Exploit Publication Causes Public Awareness

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

{% include-markdown "./pxa_diagram.md" %}

down to the following:

{% include-markdown "./pxa_diagram_simple.md" %}

### Attacks Do Not Necessarily Cause Public Awareness

In this model, attacks observed when a vulnerability is unknown to the
public ($\cdot\cdot\cdot p \cdot A$) need not immediately cause public awareness
($\cdot\cdot\cdot P \cdot A$), although, obviously, that can and does happen.
Our reasoning for allowing states in $\cdot\cdot\cdot p \cdot A$ to persist is
twofold:

1. The connection between attacks and exploited vulnerabilities
    is often made later during incident analysis. While the attack
    itself may have been observed much earlier, the knowledge of *which*
    vulnerability it targeted may be delayed until after other events
    have occurred.
2. Attackers are not a monolithic group. An attack from a niche
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

    The probability $P$ of _public awareness_ given _attacks observed_ is
    greater than the probability of _public awareness_ without _attacks observed_.

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

Following the complete state machine diagram above, we can summarize the transition functions of the CS model as a
right-linear grammar $\delta^{cs}$.

???+ note "CS Transition Function ($\delta^{cs}$) Defined"

    $\delta^{cs} =
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
        \end{cases}$

!!! tip "For more information"

    A more thorough examination of the strings generated by this grammar,
    their interpretation as the possible histories of all CVD cases, and implications for measuring the efficacy of the 
    overall CVD process writ large can be found in [A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=735513).
