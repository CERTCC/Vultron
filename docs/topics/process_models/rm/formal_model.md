---
stakeholder_type: [platform-developer, process-researcher]
level: 400
---

# RM Formal Model

This page defines the Report Management (RM) process as a deterministic finite automaton (DFA).
It is for readers who want the formal model behind the [RM process model](index.md), which describes each state and transition in practitioner terms.
The [formal protocol](../../../reference/formal_protocol/index.md) builds on the definitions given here.

The normative RM states and transitions are specified in [§6 of the Vultron Protocol Specification](../../../reference/vultron-spec/index.md#6-report-management-rm-state-machine-n).
The [states table (§6.1)](../../../reference/vultron-spec/index.md#61-states) and the [transitions table (§6.2)](../../../reference/vultron-spec/index.md#62-transitions-and-guards) are the authority.
This page restates them in DFA notation and adds what the specification does not carry: the symbol set, a right-linear grammar, the shortest possible histories, and a set of named state subsets that other process-model pages use.

---

## The DFA notation

{% include-markdown "../_dfa_notation_definition.md" %}

A DFA is a 5-tuple of states, an initial state, a set of final states, a set of input symbols, and a transition function.
The inset at right defines each element.
The sections below give each element for the RM process in turn.

## RM states

???+ note inline end "RM States $\mathcal{Q}^{rm}$ Defined"

    $\begin{split}
        \mathcal{Q}^{rm} = \{ & \underline{S}tart, \\
                              & \underline{R}eceived,\\
                              & \underline{I}nvalid, \\
                              & \underline{V}alid, \\
                              & \underline{A}ccepted, \\
                              & \underline{D}eferred, \\
                              & \underline{C}losed \}
        \end{split}$

The RM DFA has seven states, shown at right.
The underlined capital letter of each state name is its shorthand, so *Received* is *R* and *Closed* is *C*.
Each Participant in a case has its own RM state.
The [RM process model](index.md#rm-states) describes what each state means for a Participant.

## Start and end states

???+ note "RM Start and End States ($q^{rm}_0, \mathcal{F}^{rm}$) Defined"

    The RM process starts in the _Start_ state.

    $$q^{rm}_0 = Start$$

    The RM process ends in the _Closed_ state.

    $$\mathcal{F}^{rm} = \{Closed\}$$

*Start* is a placeholder for a report the Participant has not yet received.
It is useful when modeling coordination across several Participants, where one Participant already holds a report that another has not yet seen.

## RM symbols

???+ note inline end "RM Symbols ($\Sigma^{rm}$) Defined"

    $\begin{align*}
      \Sigma^{rm} = \{ & \underline{r}eceive, \\
                       & \underline{v}alidate, \\
                       & \underline{i}nvalidate, \\
                       & \underline{a}ccept, \\
                       & \underline{d}efer, \\
                       & \underline{c}lose \}
    \end{align*}$

The actions a Participant performs in the RM process are the symbols of the DFA.
There are six, shown at right, each abbreviated by its underlined lowercase letter.
They are the triggers of the specification's transitions table, and each one corresponds to an RM protocol message: receipt of a Report Submission (RS), Report Validated (RV), Report Invalidated (RI), Report/Case Accepted (RA), Report/Case Deferred (RD), and Report Closed (RC).
The [formal protocol messages](../../../reference/formal_protocol/messages.md) page defines those messages.

## RM transition function

???+ note inline end "RM Transition Function ($\delta^{rm}$) Defined"

    $$\delta^{rm} =
    \begin{cases}
    S & \to rR \\
    R & \to vV~|~iI \\
    I & \to vV~|~cC \\
    V & \to aA~|~dD \\
    A & \to dD~|~cC \\
    D & \to aA~|~cC \\
    C & \to \epsilon \\
    \end{cases}$$

The transition function is written at right as a right-linear grammar.
Each production reads as "from this state, this symbol leads to that state".
For example, $R \to vV~|~iI$ says that a *Received* report moves to *Valid* on *validate* and to *Invalid* on *invalidate*.

The grammar has one production alternative for each of the eleven transitions in the specification's transitions table, and no others.
The [RM state machine diagram](index.md#rm-state-transitions) shows the same transitions.

## Possible RM histories

The strings the grammar generates are the possible sequences of actions one Participant can take on one report.
There are 15 such strings of length seven or less: *ric*, *rvac*, *rvdc*, *rivac*, *rivdc*, *rvadc*, *rvdac*, *rivadc*, *rivdac*, *rvadac*, *rvdadc*, *rivadac*, *rivdadc*, *rvadadc*, and *rvdadac*.

Longer strings only add *defer*–*accept* (*da*) or *accept*–*defer* (*ad*) cycles before closure (*c*).
RM processes are usually short, and Participants tend to avoid frequent starts and stops.
We therefore expect most reports to follow one of the strings above, with the rest falling into marginal extensions of them.

!!! tip "See also"

    A [reward function](../../measuring_cvd/reward_functions.md) for evaluating RM strings is discussed as future work.

## The RM DFA fully defined

!!! note "RM DFA Fully Defined"

    Taken in combination, the full definition of the RM DFA is as follows:

    $$  RM =
        \begin{pmatrix}
                \begin{aligned}
                    \mathcal{Q}^{rm} = & \{ S,R,I,V,A,D,C \} \\
                    q^{rm}_0 = & S  \\
                    \mathcal{F}^{rm} = & \{ C \} \\
                    \Sigma^{rm} = & \{ r,i,v,a,d,c \} \\
                    \delta^{rm} = &
                        \begin{cases}
                            S \to & rR \\
                            R \to & vV~|~iI \\
                            I \to & vV~|~cC \\
                            V \to & aA~|~dD \\
                            A \to & dD~|~cC \\
                            D \to & aA~|~cC \\
                            C \to & \epsilon \\
                        \end{cases}
                \end{aligned}
        \end{pmatrix}$$

## RM state subsets

Other process-model pages refer to groups of RM states by name.
The subsets below define those names.

???+ note "RM State Subsets Defined"

    $$  \begin{align}
            Open &= \{ R,I,V,D,A \} \\
            Valid~Yet~Unclosed &= \{ V,D,A \} \\
            Potentially~Valid~Yet~Unclosed &= \{ R,V,D,A\} \\
            Active &= \{ R,V,A \} \\
            Inactive &= \{ I,D,C \}
        \end{align}$$

Two of these subsets have direct counterparts in the reference implementation.
*Active* is `RM_ACTIVE`, and *Valid Yet Unclosed* is `RM_VALIDATED`, both in `vultron/core/states/rm.py`.
The [RM and EM interactions](../model_interactions/rm_em.md) page uses these subsets to say when embargo negotiation may proceed.
