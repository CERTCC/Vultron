# Sequences of Events and Possible Histories in CVD

{% include-markdown "../../includes/not_normative.md" %}

In [Case State Events](../process_models/cs/events.md), we
began by identifying a set of events of interest in
CVD cases. Then we
constructed a state model describing how the occurrence of these events
can interact with each other. In this section, we look at paths through
the resulting state model.


## Sequences of Events

Before we can discuss the possible histories of CVD, we need to define
the concept of a sequence of events.

!!! note "Sequences Formally Defined"

    A sequence $s$ is an ordered set of some number of events
    $\sigma_i \in \Sigma$ for $1 \leq i \leq n$ and the length of $s$ is
    $|s| \stackrel{\mathsf{def}}{=}n$.

    In other words, a sequence $s$ is an
    input string to the DFA defined in the [CVD Case State Model](../process_models/cs/cs_model.md).

    $$s \stackrel{\mathsf{def}}{=}\left( \sigma_1, \sigma_2, \dots \sigma_n \right)$$

## Case Histories

{% include-markdown "../process_models/cs/_events_sigma.md" %}

Armed with the definition of a sequence, we can now define a history.

!!! note "Vulnerability Disclosure Case History Formally Defined"

    A vulnerability disclosure case history $h$ is a sequence $s$ containing one
    and only one of each of the symbols in $\Sigma$; by definition
    $|h| = |\Sigma| = 6$. Note this is a slight abuse of notation;
    $|\textrm{ }|$ represents both sequence length and the cardinality of a
    set.

    $$\begin{split}
        h \stackrel{\mathsf{def}}{=}s : & \forall \sigma_i, \sigma_j \in s \textrm{ it is the case that } \sigma_i \neq \sigma_j \textrm{ and } \\
        & \forall \sigma_k \in \Sigma \textrm{ it is the case that } \exists \sigma_i \in s \textrm{ such that } \sigma_k = \sigma_i 
    \end{split}
    $$

    where two members of the set $\Sigma$ are equal if they are represented
    by the same symbol and not equal otherwise.

The set of all potential histories, $\mathcal{H}_p$, is a set of all the sequences $h$ that
satisfy this definition.

## The Possible Histories of CVD

Given that a history $h$ contains all six events $\Sigma$ in some order,
there could be at most 720 ($_{6} \mathrm{P}_{6} = 6! = 720$) potential
histories. However, because of the causal requirements outlined in
[CS Transitions](../process_models/cs/transitions.md), we know that Vendor
Awareness (**V**) must precede Fix Ready (**F**) and that Fix Ready
must precede Fix Deployed (**D**).

The DFA developed
in [CS Process Model](../process_models/cs/model_definition.md) provides
the mechanism to validate histories: a history $h$ is valid if the
DFA accepts it as a valid input string. Once this constraint is applied,
only 70 possible histories $h \in \mathcal{H}p$ remain viable.
We denote the set of all
such valid histories as $\mathcal{H}$ and have $|\mathcal{H}| = 70$. The
set of possible histories $\mathcal{H}$ corresponds to the 70 allowable
paths through $\mathcal{Q}^{CS}$ as can be derived from the CS transition
function $\delta^{CS}$ in [CS Transitions](../process_models/cs/transitions.md).
and the diagram in
[Case State Model Definition](../process_models/cs/model_definition.md).

!!! info "Other Definitions Used in the Table Below"

    - The skill ranking function on the histories is defined in
    [Discriminating Skill from Luck](./discriminating_skill_and_luck.md).
    - The desirability of the history ($\mathbb{D}^h$) is defined in
    [On the Desirability of Possible Histories](./desirable_histories.md).
    - The expected frequency of each history $f_h$ is explained in
    [Reasoning Over Histories](./reasoning_over_histories.md).


!!! info "Table of Possible Histories"

  The set of possible histories $\mathcal{H}$ is listed exhaustively in
  the table below.

  {% include-markdown "./_table_possible_histories.md" %}


Now that we have defined the set of histories $\mathcal{H}$, we can
summarize the effects of the transition function $\delta$ developed in
[CS Transitions](../process_models/cs/transitions.md) as a set of patterns it imposes on all
histories $h \in \mathcal{H}$:

1. The causality constraint of the vendor fix path must hold.
2. The model makes the simplifying assumption that vendors know at
least as much as the public does. In other words, all histories must
meet one of two criteria: either Vendor Awareness precedes Public
Awareness (**P**) or Vendor Awareness must immediately follow it.
3. The model assumes that the public can be informed about a
vulnerability by a public exploit. Therefore, either Public Awareness
precedes Exploit Public (**X**) or must immediately follow it.

{% include-markdown "./_history_constraints.md" %}

This model is amenable for analysis of CVD, but we need to add a way to express
preferences before it is complete. That is the subject of the [Desirable Histories](./desirable_histories.md) section.