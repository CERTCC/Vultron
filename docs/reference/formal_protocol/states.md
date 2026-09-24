---
stakeholder_type: [platform-developer, process-researcher]
level: 400
---

# States

{% include-markdown "../../includes/normative.md" %}

This page defines $S_i$, the states of each participant process, and $o_i$, its start state: the first two elements of the protocol quadruple introduced in [Protocol Definition](protocol_definition.md).

Each Participant in a Multi-Party Coordinated Vulnerability Disclosure (MPCVD) case has a corresponding Report Management (RM) state, an Embargo Management (EM) state, and an overall Case State (CS) state.
Therefore, a Participant's state can be represented as a triple comprising the state of each of these models.

!!! note "*Participant State*"

    A Participant's state is a triple comprising the state of each of the RM, EM, and CS models.

    $$q_{Participant} = (q^{rm},q^{em},q^{cs})$$

Good Participant situation awareness makes for good Coordinated Vulnerability Disclosure (CVD) decision making.

!!! note ""

    Participants SHOULD track the state of other Participants in a case 
    to inform their own decision making as it pertains to the case.

An example [case model](../../topics/case_lifecycle/case_model.md) that facilitates such tracking appears elsewhere.
However, the Vultron protocol is expected to function even when incomplete information is available to
any given Participant.

!!! note ""  

    Adequate operation of the protocol MUST NOT depend on perfect information across all Participants.

A generic state model for a CVD Participant can be composed from the Cartesian product of $\mathcal{Q}^{rm}$,
$\mathcal{Q}^{em}$, and $\mathcal{Q}^{cs}$ as shown below.

!!! note "*Participant State Space*"

    A Participant's state is a triple comprising the state of each of the RM, EM, and CS models.
    The set of all possible Participant states is the Cartesian product of the RM, EM, and CS state sets.

    $$  S_i 
        % = \mathcal{Q}^{rm} \times \mathcal{Q}^{em} \times \mathcal{Q}^{cs}
        = 
        \underbrace{
        \begin{bmatrix}
            S \\
            R \\
            I \\
            V \\
            D \\
            A \\ 
            C \\
        \end{bmatrix}
        }_{\mathcal{Q}^{rm}}
        \times 
        % embargo state
        \underbrace{
        \begin{bmatrix}
            N \\
            P \\
            A \\
            R \\
            X \\
        \end{bmatrix}
        }_{\mathcal{Q}^{em}}
        \times 
        % case state
        \underbrace{
        \begin{bmatrix}
            \begin{bmatrix}
                \varnothing \\
                vfd \\
                Vfd \\
                VFd \\
                VFD \\
            \end{bmatrix}
            \times 
            \begin{bmatrix}
                p \\
                P
            \end{bmatrix}
            \times 
            \begin{bmatrix}
                x \\
                X
            \end{bmatrix}
            \times 
            \begin{bmatrix}
                a \\
                A
            \end{bmatrix}
        \end{bmatrix}
        }_{\mathcal{Q}^{cs}}$$

Note that the above definition splits the case state
($\mathcal{Q}^{cs}$) into chunks corresponding to the Vendor fix path
($vfd \xrightarrow{\mathbf{V}} Vfd \xrightarrow{\mathbf{F}} VFd \xrightarrow{\mathbf{D}} VFD$)
and the public-exploit-attack ($pxa \xrightarrow{\dots} PXA$) sub-models
from the [Case State Model](../../topics/process_models/cs/index.md).
This is done for two reasons.
First, it gives a more compact notation for representing the 32 states of the CS model.
Second, as described in [Model Interactions](../../topics/process_models/model_interactions/index.md), it highlights the fact that
the Vendor fix path represents the state of an individual Participant, whereas the public-exploit-attack sub-model
represents facts about the world at large.
Because not all Participants
are Vendors or Deployers, Participants might not have a corresponding
state on the $vfd \xrightarrow{} VFD$ axis. Therefore, a null
element $\varnothing$ is added to the set of states representing the Vendor fix
path.

When a case state is written for a particular role, the fix-path letters that do not apply to it are left out rather than written as $\varnothing$.
So $dpxa$ is the case state of a Deployer, who tracks deployment but not the Vendor's awareness or fix, and $pxa$ is the case state of a Participant with no place on the fix path at all.
For a Deployer the fix path narrows to $\{d, D\}$, a role-specific restriction of the set above rather than one of its elements.
[Starting States](#starting-states) uses this notation.

## Unreachable States

For any Participant, the RM $Closed$ state implies that the EM and CVD Case states do
not matter.
Similarly, for any Participant, the RM $Start$ state represents a case that the
Participant doesn't even know about yet.
Therefore, the $Start$ state also implies that the EM and CVD Case states do not matter.
The symbol $*$ represents the "don't care" value.

???+ note "Unreachable EM and CS States when RM is in  *Closed* or *Start*"

    $$q^{rm} \in \{S,C\} \implies (q^{em} \in *) \cup (q^{cs} \in *)$$

A public exploit implies the vulnerability is public as well. In other
words, $q^{cs} \in \cdot\cdot\cdot pX \cdot$ is an ephemeral state that resolves
quickly to $q^{cs} \in \cdot\cdot\cdot PX \cdot$. (As a reminder, dots ($\cdot$)
in CVD case state notation indicate single-character wildcards.)

???+ note "Unreachable CS States when CS is in *Public* or *Exploit*"

    $$q^{cs} \in \cdot\cdot\cdot pX \cdot \implies q^{cs} \in \cdot\cdot\cdot PX \cdot$$

Furthermore, when a vulnerability becomes public, the EM state no longer matters.

???+ note "Unreachable EM States when CS is in *Public*"

    $$q^{cs} \in \cdot\cdot\cdot PX \cdot \implies q^{em} \in *$$

Taken together, these limitations narrow the state model.
The result is shown below.

!!! note "Participant States With Unreachable States Removed"

    $$  S_i 
        % = \mathcal{Q}^{rm} \times \mathcal{Q}^{em} \times \mathcal{Q}^{cs}
        = 
        \begin{cases}
        (S, *, *)\\
        {}\\
        \begin{bmatrix}
            R \\
            I \\
            V \\
            D \\
            A \\ 
        \end{bmatrix}
        \times 
        % embargo state
        \begin{bmatrix}
            N \\
            P \\
            A \\
            R \\
            X \\
        \end{bmatrix}
        \times 
        % case state
        \begin{bmatrix}
            \begin{bmatrix}
                \varnothing \\
                vfd \\
                Vfd \\
                VFd \\
                VFD \\
            \end{bmatrix}
            \times 
            \begin{bmatrix}
                p \\
            \end{bmatrix}
            \times 
            \begin{bmatrix}
                x \\
            \end{bmatrix}
            \times 
            \begin{bmatrix}
                a \\
                A \\
            \end{bmatrix}
        \end{bmatrix} \\
        {} \\
        \begin{bmatrix}
            R \\
            I \\
            V \\
            D \\
            A \\ 
        \end{bmatrix}
        \times 
        % embargo state
        \begin{bmatrix}
        * \\
        \end{bmatrix}
        \times 
        % case state
        \begin{bmatrix}
            \begin{bmatrix}
                \varnothing \\
                vfd \\
                Vfd \\
                VFd \\
                VFD \\
            \end{bmatrix}
            \times 
            \begin{bmatrix}
                P
            \end{bmatrix}
            \times 
            \begin{bmatrix}
                x \\
                X
            \end{bmatrix}
            \times 
            \begin{bmatrix}
                a \\
                A
            \end{bmatrix}
        \end{bmatrix} \\
        {}\\
        (C, *, *) \\
        \end{cases}$$

The role a participant plays restricts its reachable states further: for example, only Vendors traverse the whole $vfd \xrightarrow{} VFD$ fix path.
[About the Size of the Protocol State Space](../../topics/measuring_cvd/state_space_size.md) counts the reachable states for each role and estimates the size of a whole case's state space.

## Starting States

Each Participant begins a case in the state where the report management
process is in the start state, there is no embargo in place, and the
case has not made any progress.

!!! note "Participant Start State Formally Defined"

    $$o_i = (o_i^{rm},~o_i^{em},~o_i^{cs}) = (S,N,vfdpxa)$$

Because a participant's role determines which parts of the Vendor fix path apply to it, the starting states differ by role, as shown below.

!!! note "Participant Start States"

    | Participant Role | Start State ($o_i$)|
    |------------------|-------------|
    | Vendor           | $(S,N,vfdpxa)$ |
    | Deployer         | $(S,N,dpxa)$ |
    | Other            | $(S,N,pxa)$ |
    | Finder/Reporter  | $(A,N,pxa)$ |

For a case to really begin, the Finder must at least reach the $A$ state.
Therefore, at the point when a second party finds out about the vulnerability from a Finder,
the Finder/Reporter is presumed to be already at $q_{Finder}=(A, N, pxa)$.

[Messages](messages.md) defines the message types Participants exchange, and [Transitions](transitions.md) shows how those messages move a Participant between these states.
