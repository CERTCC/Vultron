# Sequences of Events and Possible Histories in CVD

In [Case State Events](../process_models/cs/events.md), we
began by identifying a set of events of interest in
CVD cases. Then we
constructed a state model describing how the occurrence of these events
can interact with each other. In this section, we look at paths through
the resulting state model.

## Sequences of Events

!!! note "Sequences Formally Defined"

    A sequence $s$ is an ordered set of some number of events
    $\sigma_i \in \Sigma$ for $1 \leq i \leq n$ and the length of $s$ is
    $|s| \stackrel{\mathsf{def}}{=}n$.

    In other words, a sequence $s$ is an
    input string to the DFA defined in
    §[2](#sec:model){== TODO fix ref to sec:model ==}.

    $$s \stackrel{\mathsf{def}}{=}\left( \sigma_1, \sigma_2, \dots \sigma_n \right)$$

## Case Histories

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
paths through $\mathcal{Q}$ as can be derived from Table
[2.6](#tab:delta_vfdpxa){== TODO fix ref to tab:delta_vfdpxa ==} and Fig.
[2.4](#fig:vfdpxa_map){== TODO fix ref to fig:vfdpxa_map ==}.

The set of possible histories $\mathcal{H}$ is listed exhaustively in
the table below. 
The skill ranking function on the histories will be defined in
§[4.4](#sec:h_poset_skill){== TODO fix ref to sec:h_poset_skill ==}. The desirability of the history
($\mathbb{D}^h$) will be defined in
§[3.2](#sec:desirability){== TODO fix ref to sec:desirability ==}. The expected frequency of each history
$f_h$ is explained in
§[4.1](#sec:history_frequency_analysis){== TODO fix ref to sec:history_frequency_analysis ==}.


| # |            $h \in \mathcal{H}$             | rank | $\mathbb{D}^h$ count |  $f_h$ | 
| :---: |:------------------------------------------:| :--: |:--------------------:|-------:| 
| 0 | (**A**, **X**, **P**, **V**, **F**, **D**) | 1 |          0           | 0.0833 |
| 1 | (**A**, **P**, **V**, **X**, **F**, **D**) | 2 |          2           | 0.0417 |
| 2 | (**A**, **V**, **X**, **P**, **F**, **D**) | 3 |          2           | 0.0278 |
| 3 | (**X**, **P**, **V**, **A**, **F**, **D**) | 4 |          3           | 0.1250 |
| 4 | (**V**, **A**, **X**, **P**, **F**, **D**) | 5 |          3           | 0.0208 |
| 5 | (**P**, **V**, **A**, **X**, **F**, **D**) | 6 |          4           | 0.0417 |
| 6 | (**A**, **V**, **P**, **X**, **F**, **D**) | 7 |          3           | 0.0139 |
| 7 | (**A**, **P**, **V**, **F**, **X**, **D**) | 7 |          3           | 0.0208 |
| 8 | (**X**, **P**, **V**, **F**, **A**, **D**) | 8 |          4           | 0.0625 |
| 9 | (**V**, **A**, **P**, **X**, **F**, **D**) | 9 |          4           | 0.0104 |
| 10 | (**P**, **V**, **X**, **A**, **F**, **D**) | 10 |          5           | 0.0417 |
| 11 | (**V**, **P**, **A**, **X**, **F**, **D**) | 11 |          5           | 0.0104 |
| 12 | (**P**, **V**, **A**, **F**, **X**, **D**) | 11 |          5           | 0.0208 |
| 13 | (**V**, **X**, **P**, **A**, **F**, **D**) | 11 |          5           | 0.0312 |
| 14 | (**A**, **V**, **P**, **F**, **X**, **D**) | 12 |          4           | 0.0069 |
| 15 | (**A**, **P**, **V**, **F**, **D**, **X**) | 13 |          4           | 0.0208 |
| 16 | (**V**, **A**, **P**, **F**, **X**, **D**) | 14 |          5           | 0.0052 |
| 17 | (**X**, **P**, **V**, **F**, **D**, **A**) | 15 |          5           | 0.0625 |
| 18 | (**P**, **V**, **X**, **F**, **A**, **D**) | 16 |          6           | 0.0208 |
| 19 | (**A**, **V**, **F**, **X**, **P**, **D**) | 17 |          4           | 0.0093 |
| 20 | (**V**, **P**, **X**, **A**, **F**, **D**) | 18 |          6           | 0.0104 |
| 21 | (**P**, **V**, **F**, **A**, **X**, **D**) | 19 |          6           | 0.0139 |
| 22 | (**V**, **X**, **P**, **F**, **A**, **D**) | 19 |          6           | 0.0156 |
| 23 | (**V**, **P**, **A**, **F**, **X**, **D**) | 20 |          6           | 0.0052 |
| 24 | (**V**, **A**, **F**, **X**, **P**, **D**) | 21 |          5           | 0.0069 |
| 25 | (**P**, **V**, **A**, **F**, **D**, **X**) | 22 |          6           | 0.0208 |
| 26 | (**A**, **V**, **P**, **F**, **D**, **X**) | 23 |          5           | 0.0069 |
| 27 | (**A**, **V**, **F**, **P**, **X**, **D**) | 24 |          5           | 0.0046 |
| 28 | (**P**, **V**, **F**, **X**, **A**, **D**) | 25 |          7           | 0.0139 |
| 29 | (**V**, **P**, **X**, **F**, **A**, **D**) | 25 |          7           | 0.0052 |
| 30 | (**V**, **A**, **P**, **F**, **D**, **X**) | 26 |          6           | 0.0052 |
| 31 | (**V**, **A**, **F**, **P**, **X**, **D**) | 27 |          6           | 0.0035 |
| 32 | (**P**, **V**, **X**, **F**, **D**, **A**) | 28 |          7           | 0.0208 |
| 33 | (**V**, **P**, **F**, **A**, **X**, **D**) | 29 |          7           | 0.0035 |
| 34 | (**V**, **F**, **A**, **X**, **P**, **D**) | 30 |          6           | 0.0052 |
| 35 | (**V**, **X**, **P**, **F**, **D**, **A**) | 31 |          7           | 0.0156 |
| 36 | (**P**, **V**, **F**, **A**, **D**, **X**) | 32 |          7           | 0.0139 |
| 37 | (**V**, **P**, **A**, **F**, **D**, **X**) | 33 |          7           | 0.0052 |
| 38 | (**V**, **P**, **F**, **X**, **A**, **D**) | 34 |          8           | 0.0035 |
| 39 | (**A**, **V**, **F**, **P**, **D**, **X**) | 35 |          6           | 0.0046 |
| 40 | (**V**, **F**, **A**, **P**, **X**, **D**) | 36 |          7           | 0.0026 |
| 41 | (**V**, **P**, **X**, **F**, **D**, **A**) | 37 |          8           | 0.0052 |
| 42 | (**P**, **V**, **F**, **X**, **D**, **A**) | 37 |          8           | 0.0139 |
| 43 | (**V**, **A**, **F**, **P**, **D**, **X**) | 38 |          7           | 0.0035 |
| 44 | (**V**, **P**, **F**, **A**, **D**, **X**) | 39 |          8           | 0.0035 |
| 45 | (**V**, **F**, **P**, **A**, **X**, **D**) | 40 |          8           | 0.0026 |
| 46 | (**V**, **F**, **X**, **P**, **A**, **D**) | 41 |          8           | 0.0078 |
| 47 | (**A**, **V**, **F**, **D**, **X**, **P**) | 42 |          6           | 0.0046 |
| 48 | (**P**, **V**, **F**, **D**, **A**, **X**) | 43 |          8           | 0.0139 |
| 49 | (**V**, **A**, **F**, **D**, **X**, **P**) | 44 |          7           | 0.0035 |
| 50 | (**V**, **P**, **F**, **X**, **D**, **A**) | 45 |          9           | 0.0035 |
| 51 | (**V**, **F**, **A**, **P**, **D**, **X**) | 46 |          8           | 0.0026 |
| 52 | (**V**, **F**, **P**, **X**, **A**, **D**) | 46 |          9           | 0.0026 |
| 53 | (**A**, **V**, **F**, **D**, **P**, **X**) | 47 |          7           | 0.0046 |
| 54 | (**P**, **V**, **F**, **D**, **X**, **A**) | 48 |          9           | 0.0139 |
| 55 | (**V**, **P**, **F**, **D**, **A**, **X**) | 49 |          9           | 0.0035 |
| 56 | (**V**, **F**, **X**, **P**, **D**, **A**) | 50 |          9           | 0.0078 |
| 57 | (**V**, **F**, **P**, **A**, **D**, **X**) | 51 |          9           | 0.0026 |
| 58 | (**V**, **A**, **F**, **D**, **P**, **X**) | 52 |          8           | 0.0035 |
| 59 | (**V**, **F**, **A**, **D**, **X**, **P**) | 53 |          8           | 0.0026 |
| 60 | (**V**, **P**, **F**, **D**, **X**, **A**) | 54 |          10          | 0.0035 |
| 61 | (**V**, **F**, **P**, **X**, **D**, **A**) | 55 |          10          | 0.0026 |
| 62 | (**V**, **F**, **A**, **D**, **P**, **X**) | 56 |          9           | 0.0026 |
| 63 | (**V**, **F**, **P**, **D**, **A**, **X**) | 57 |          10          | 0.0026 |
| 64 | (**V**, **F**, **D**, **A**, **X**, **P**) | 58 |          9           | 0.0026 |
| 65 | (**V**, **F**, **P**, **D**, **X**, **A**) | 59 |          11          | 0.0026 |
| 66 | (**V**, **F**, **D**, **A**, **P**, **X**) | 60 |          10          | 0.0026 |
| 67 | (**V**, **F**, **D**, **X**, **P**, **A**) | 61 |          11          | 0.0052 |
| 68 | (**V**, **F**, **D**, **P**, **A**, **X**) | 61 |          11          | 0.0026 |
| 69 | (**V**, **F**, **D**, **P**, **X**, **A**) | 62 |          12          | 0.0026 |


Now that we have defined the set of histories $\mathcal{H}$, we can
summarize the effects of the transition function $\delta$ developed in
§[2.4](#sec:transitions){== TODO fix ref to sec:transitions ==} (Table
[2.6](#tab:delta_vfdpxa){== TODO fix ref to tab:delta_vfdpxa ==}) as a set of patterns it imposes on all
histories $h \in \mathcal{H}$:

!!! note inline end "Formalisms"

    _Vendor Fix Path_ causality must hold

    $$\mathbf{V} \prec \mathbf{F} \prec \mathbf{D}$$
  
    _Vendor Awareness_ precedes or is caused by _Public Awareness_

    $$\mathbf{V} \prec \mathbf{P} \textrm{ or } \mathbf{P} \rightarrow \mathbf{V}$$

    _Public Awareness_ precedes or is caused by _Exploit Public_

    $$\mathbf{P} \prec \mathbf{X} \textrm{ or } \mathbf{X} \rightarrow \mathbf{P}$$

 
- First, the causality constraint of the
vendor fix path must hold. 

- Second, the model makes the simplifying assumption that vendors know at
least as much as the public does. In other words, all histories must
meet one of two criteria: either Vendor Awareness precedes Public
  Awareness (**P**) or Vendor Awareness must immediately follow it.

- Third, the model assumes that the public can be informed about a
vulnerability by a public exploit. Therefore, either Public Awareness
precedes Exploit Public (**X**) or must immediately follow it.


This model is amenable for analysis of CVD, but we need to add a way to express
preferences before it is complete. Thus we are part way through **RQ1**.
§[6.2](#sec:mpcvd){== TODO fix ref to sec:mpcvd ==} will
address how this model can generalize from CVD to MPCVD.

