---
stakeholder_type: [platform-developer, process-researcher]
level: 400
page_type: explanation
subject: protocol
introduces: [Embargo Grammar]
description: >
  The EM process as a formal state machine, with its grammar and every possible history.
---

# EM Formal Model

{% include-markdown "../../../includes/specification_governs.md" %}

This page defines the Embargo Management (EM) process as a deterministic finite automaton (DFA).
It is for readers who want the formal model behind the [EM process model](index.md).
That page describes each state and transition in practitioner terms.
The [formal protocol](../../../reference/formal_protocol/index.md) builds on the definitions given here.

The normative EM states and transitions are specified in [§7 Embargo Management (EM) State Machine in the Vultron Protocol Specification](../../../reference/vultron-spec/tracking-models.md#7-embargo-management-em-state-machine-n).
The states table in [§7.1 States](../../../reference/vultron-spec/tracking-models.md#71-states) and the transitions table in [§7.2 Transitions and Guards](../../../reference/vultron-spec/tracking-models.md#72-transitions-and-guards) are the authority.
This page restates them in DFA notation.
It also adds four things that the specification does not carry: the symbol set, a right-linear grammar, a regular expression for every history the transitions admit, and the shortest histories.

A case's EM state is never set directly.
It is computed from the case's embargo register, which holds one entry per embargo ever proposed ([§7.1.2 Deriving EM from the Register](../../../reference/vultron-spec/tracking-models.md#712-deriving-em-from-the-register)).
Every change to the register must obey the transitions on this page (ADR-0130).

{% include-markdown "./_em_state_names.md" %}

---

## The DFA notation

{% include-markdown "../_dfa_notation_definition.md" %}

A DFA is a 5-tuple of states, an initial state, a set of final states, a set of input symbols, and a transition function.
The inset at right defines each element.
The sections below give each element for the EM process in turn.

## EM states

???+ note inline end "EM States ($\mathcal{Q}^{em}$) Defined"

    $\begin{split}
        \mathcal{Q}^{em} = \{ & \underline{N}one, \\
        & \underline{P}roposed, \\
        & \underline{A}ctive, \\
        & \underline{R}evise, \\
        & e\underline{X}ited \}
    \end{split}$

A case is either under an active embargo or it is not.
Because embargo management coordinates several Participants, the model separates two further situations from those two.

- *Proposed* sits between *None* and *Active*: an embargo has been proposed but not yet accepted or rejected.
- *Revise* sits alongside *Active*: an embargo is in force and a change to it has been proposed but not yet accepted or rejected.

The model also separates the case that has never had an embargo (*None*) from the case whose embargo has ended (*eXited*).
Combining these gives the five states of $\mathcal{Q}^{em}$, shown at right.

The underlined capital letters are the shorthand used for EM states in the rest of this documentation.

!!! warning "Check which model a shorthand letter belongs to"

    $q^{em} \in A$ is distinct from $q^{rm} \in A$.
    An embargo can be *Active* while a report is [*Accepted*](../rm/index.md#the-accepted-a-state), and the two are independent.

## Start and final states

???+ note inline end "EM Start and Final States Defined"

    $q^{em}_0 = None$

    $\mathcal{F}^{em} = \{None,~eXited\}$

The EM process starts in *None*.
It ends in one of two states.
If an embargo is ever agreed, the process ends in *eXited* once that embargo ends.
If no embargo is ever agreed, the process ends in *None*.

## EM symbols

???+ note inline end "EM Symbols ($\Sigma^{em}$) Defined"

    $$\begin{split}
        \Sigma^{em} = \{
         ~\underline{p}ropose,
         ~\underline{r}eject,
         ~\underline{a}ccept,
         ~\underline{t}erminate
        \}
    \end{split}$$

Four actions drive the machine.

- An embargo MAY be *proposed*.
- Once proposed, it MAY be *accepted* or *rejected*.
- Once accepted, revisions MAY be *proposed*, and each MAY in turn be *accepted* or *rejected*.
- An accepted embargo MUST eventually *terminate*.

The underlined lowercase letters are the shorthand for EM transitions in the rest of this documentation.

## EM state transitions

The diagram in the [EM process model](index.md#em-state-transitions) shows the whole machine.
The four subsections below take each part of it in turn.

### Propose embargo

A new embargo is proposed when none exists.

```mermaid
stateDiagram-v2
    direction LR
    dots: ...
    [*] --> None
    None --> Proposed: propose
    Proposed --> dots
    dots --> [*]
```

### Accept or reject an embargo proposal

Once an embargo is proposed, it is accepted or rejected.
A further proposal made while the first is outstanding is added beside it.
Both proposals stay open, and the case stays at *Proposed*.
Rejecting one of several open proposals leaves the others open, so the case stays at *Proposed*.
Accepting one of several proposals makes it the embargo in force.
The others stay open as revisions of it, so the case moves to *Revise* rather than *Active*.
The case reaches *None* or *Active* only when the last open proposal is rejected or accepted.

```mermaid
stateDiagram-v2
    direction LR
    [*] --> None
    None --> Proposed
    state Proposed {
        direction LR
        eval: Accept or reject?
        state choose <<choice>>
        [*] --> eval
        eval --> choose
    }
    choose --> Active: accept (none left open)
    choose --> Revise: accept (others open)
    choose --> None: reject (none left open)
    choose --> Proposed: reject (others open)
```

### Embargo revision

Participants renegotiate an active embargo by proposing a new one.
The active embargo stays in force until an accepted revision replaces it.
If the revision is accepted, it replaces the old terms.
If the revision is rejected, the old terms stand and the case returns to *Active*, not to *None*.
Either way, the case stays at *Revise* while another revision is still open.

```mermaid
stateDiagram-v2
    direction LR
    dots: ...
    [*] --> dots
    dots --> Active
    state Revise {
        direction LR
        state choose <<choice>>
        eval: Change embargo?
        [*] --> eval
        eval --> choose
    }
    Active --> Revise: propose
    choose --> Active: accept or reject (none left open)
    choose --> Revise: accept or reject (others open)
```

!!! tip "Revisions do not interrupt active embargoes"

    Coverage never breaks during a revision.
    The existing embargo remains in effect until an accepted revision replaces it.

### Terminate embargo

An embargo terminates when its timer expires, or for the other reasons given in [Early Termination](early_termination.md).
Termination can happen while a revision is still open.

```mermaid
stateDiagram-v2
    direction LR
    dots: ...
    [*] --> dots
    dots --> Active
    dots --> Revise
    Active --> eXited: terminate
    Revise --> eXited: terminate
    eXited --> [*]
```

## A regular grammar for EM

???+ note inline end "EM Transition Function ($\delta^{em}$) Defined"

    $\delta^{em} =
        \begin{cases}
               N \to ~pP~|~\epsilon \\
               P \to ~pP~|~rN~|~rP~|~aA~|~aR \\
               A \to ~pR~|~tX \\
               R \to ~pR~|~rA~|~rR~|~aA~|~aR~|~tX \\
               X \to ~\epsilon \\
        \end{cases}$

The transitions above define the EM transition function $\delta^{em}$ as the production rules of a right-linear grammar.
The box at right writes these rules in the one-letter shorthand.
The diagram below shows the same machine in shorthand.

If you read only the symbol, four of these moves are not deterministic:

- *r* from *P* reaches *N* or stays at *P*.
- *a* from *P* reaches *A* or *R*.
- *r* or *a* from *R* reaches *A* or stays at *R*.

The register decides which move is taken.
The case moves from *P* or *R* to *N* or *A* only when no proposal remains open.
The move that stays in the same state is therefore the move made while another proposal is still open.

```mermaid
stateDiagram-v2
    direction LR
    [*] --> N
    N --> P: p
    P --> P: p, r
    P --> N: r
    P --> A: a
    P --> R: a
    A --> R: p
    A --> X: t
    R --> R: p, a, r
    R --> A: a, r
    R --> X: t
    X --> [*]
```

## Possible histories

The machine has loops at *Proposed*, at *Revise*, and between *Active* and *Revise*.
The grammar can therefore generate arbitrarily long histories.
Every complete history the transition table admits matches the regular expression `(p[pr]*r)*(p[pr]*a[par]*t)?`.
The first group is any number of negotiations that end with no embargo.
Each of these negotiations has one or more proposals, some rejected, and ends with the rejection of the last open proposal.
The optional second group is a negotiation that ends in an acceptance.
Any number of further proposals, acceptances and rejections follow while the embargo is in force.
Termination comes last, and it may come while revisions are still open.

The table admits more than the register allows.
A self-loop on *r* or *a* is legal only while another proposal is open, so a history such as *prr*, two rejections after one proposal, matches the expression but cannot happen.
The histories that a case can follow depend on the number of open proposals.
The register keeps this number, but the four symbols do not.

Here is every complete non-empty history of five or fewer actions that the table admits:

> *pr*, *pat*, *ppr*, *prr*, *paat*, *papt*, *part*, *ppat*, *pppr*, *pprr*,
> *prat*, *prpr*, *prrr*, *paaat*, *paapt*, *paart*, *papat*, *pappt*, *paprt*,
> *parat*, *parpt*, *parrt*, *ppaat*, *ppapt*, *ppart*, *pppat*, *ppppr*, *ppprr*,
> *pprat*, *pprpr*, *pprrr*, *praat*, *prapt*, *prart*, *prpat*, *prppr*, *prprr*,
> *prrat*, *prrpr*, *prrrr*

There are 3<sup>*n*−2</sup> admitted histories of length *n*, for *n* of two or more, so the list grows too quickly to extend.

EM is a scheduling process run by people, and people tolerate only so much churn in a negotiation.
Most histories in practice should therefore be near the short end of this list.
[Reward Functions](../../measuring_cvd/reward_functions.md) sketches a reward function over EM histories.

For example, a Vendor can accept the embargo that the Reporter proposes, and then propose a revision to the Vendor's preferred timeline.
This path is usually better than the alternative, where the two trade proposals and rejections and never establish an embargo.
In the worst case, where the Reporter declines to extend, a short embargo is usually better than none.
These points imply a preference for histories that begin with *pap* (propose, accept, propose a revision) over histories that begin with *ppa* or *prpa*.
[Default Embargoes](defaults.md) and the [worked protocol example](../../../tutorials/worked_example.md#vendor-accepts-then-proposes-revision) return to this idea.

## Why the shortest proposal wins

[Default Embargoes](defaults.md#rationale-for-accepting-the-shortest-proposed-embargo) recommends accepting the shorter of two proposed embargoes and proposing the longer as a revision.
This section gives the argument formally.

Suppose one Participant proposes an embargo of $n$ days and another prefers $m$ days.
Treat the embargo as a series of one-day agreements.
Represent each Participant as a vector of their willingness to keep the embargo on each day: $1$ if they are willing on that day, $0$ if not.
We assume that each Participant is willing up to some point and not after, so each vector is zero or more $1$s followed by zero or more $0$s.
For example, $[1,1,1,1,0,0,0]$ is a willingness to keep a 4-day embargo.

Let $\mathbf{x}$ and $\mathbf{y}$ be the two Participants' vectors, zero-indexed and of length $max(n,m)$:

$$\begin{aligned}
    \mathbf{x} =
        \begin{bmatrix} x_i :
        x_i =
        \begin{cases}
            1 &\text{if }i < n \\
            0 &\text{otherwise} \\
        \end{cases}
        & \text{for } 0 \leq i < max(n,m)
        \end{bmatrix} \\
    \mathbf{y} =
        \begin{bmatrix} y_i :
        y_i =
        \begin{cases}
            1 &\text{if }i < m \\
            0 &\text{otherwise}
        \end{cases}
        & \text{ for } 0 \leq i < max(n,m)
    \end{bmatrix}
\end{aligned}$$

Each vector's scalar sum is the embargo length its Participant prefers:

$$\begin{aligned}
    \Sigma(\mathbf{x}) &= n \\
    \Sigma(\mathbf{y}) &= m
\end{aligned}$$

Define the agreement vector $\mathbf{z}$ as the pairwise logical *AND* ($\wedge$) of $\mathbf{x}$ and $\mathbf{y}$:

$$\mathbf{z} =
    \begin{bmatrix} z_i :
        z_i = x_i \land y_i
        & \text{for }0 \leq i < max(n,m)
    \end{bmatrix}$$

For example, with $n=4$ and $m=7$:

$$\begin{split}
    \mathbf{x} &= [1,1,1,1,0,0,0] \\
    \wedge~\mathbf{y} &= [1,1,1,1,1,1,1] \\
    \hline
    \mathbf{z} &= [1,1,1,1,0,0,0]
\end{split}$$

The scalar sum of the agreement vector, and so the longest embargo acceptable to both parties, is the lesser of $n$ and $m$:

$$\Sigma ( \mathbf{z} ) = min(n,m)$$

## EM DFA fully defined

The note below gives the complete DFA specification for the EM process.

???+ note "EM DFA $(\mathcal{Q},q_0,\mathcal{F},\Sigma,\delta)^{em}$ Fully Defined"

    $EM =
        \begin{pmatrix}
                \begin{aligned}
                    \mathcal{Q}^{em} = & \{ N,P,A,R,X \}, \\
                    q^{em}_0 = & N, \\
                    \mathcal{F}^{em} = &\{ N,X \},  \\
                    \Sigma^{em} = &\{ p,r,a,t \}, \\
                    \delta^{em} = &
                        \begin{cases}
                           N \to ~pP~|~\epsilon \\
                           P \to ~pP~|~rN~|~rP~|~aA~|~aR \\
                           A \to ~pR~|~tX \\
                           R \to ~pR~|~rA~|~rR~|~aA~|~aR~|~tX \\
                           X \to ~\epsilon \\
                        \end{cases}
                \end{aligned}
        \end{pmatrix}$
