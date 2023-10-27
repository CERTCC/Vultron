# Reward Functions

{% include-markdown "../../includes/not_normative.md" %}

Further optimization of the Vultron Protocol can be studied with the
development of reward functions to evaluate preferences for certain
CVD case histories
over others.
In [A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=735513),
we provided a method to measure skill (${\alpha}_d$) in CVD based on a partial order over the CVD success criteria that make up the CS process, as outlined in
[Defining CVD Success](../background/cvd_success.md).
While not yet a fully-realized reward function, we feel that the ${\alpha}_d$ skill measure has potential as the basis
of a reward function for the CS model.

The following sections describe two additional reward functions.

## A Reward Function for Minimizing RM Strings

In [RM State Transitions](../process_models/rm/index.md#rm-state-transitions), we described a grammar that generates
RM histories.
The state machine can generate arbitrarily long histories because of the cycles in the state machine graph;
however, we observed that human Participants in any real CVD case would likely check the amount of churn.
That sort of reliance on human intervention will not scale as well as a more automatable solution might.

As a result, we suggest that future work might produce a reward function that can be used to optimize RM histories.
Such a function would need to include the following:

- a preference for shorter paths over longer ones

- a preference for paths that traverse through $q^{rm} \in A$ over
    ones that do not

- a preference for Vendor attentiveness.

- a preference for validation accuracy

!!! tip "Notes on Vendor attentiveness"

    The default path for an organization with no CVD capability is effectively
    ${q^{em} \in S \xrightarrow{r} R \xrightarrow{i} I \xrightarrow{c}C}$,
    which is short (_good!_).
    However, assuming the vulnerability is legitimate, half of the desired CS criteria can never be achieved
    (_bad!_). 
    In other words, $\mathbf{F} \prec \mathbf{P}$, 
          $\mathbf{F} \prec \mathbf{X}$, $\mathbf{F} \prec \mathbf{A}$,
          $\mathbf{D} \prec \mathbf{P}$, $\mathbf{D} \prec \mathbf{X}$,
          $\mathbf{D} \prec \mathbf{A}$ are impossible when the Vendor ignores
          the report.
    No reward function should provide incentive for willful Vendor ignorance.

!!! tip "Notes on validation accuracy"

    Real vulnerabilities should pass through $q^{rm} \in V$, while bogus reports should pass through $q^{rm} \in I$.
    The only RM paths path not involving at least one step through $q^{rm} \in A$ are the following.

    | Path | Description |
    | ---- | ----------- |
    | $q^{rm} \in S \xrightarrow{r} R \xrightarrow{i} I \xrightarrow{c} C$ | Ignore an invalid case. |
    | $q^{rm} \in S \xrightarrow{r} R \xrightarrow{v} V \xrightarrow{d} D \xrightarrow{c} C$ | Defer a valid case. |
    | $q^{rm} \in S \xrightarrow{r} R \xrightarrow{i} I \xrightarrow{v} V \xrightarrow{d} D \xrightarrow{c} C$ | Initially ignore an invalid case, then validate, but defer it anyway. |

    To an outside observer, any of these could be interpreted as inattentiveness from an uncommunicative Participant.
    Yet any of these paths might be fine, assuming that (1) the Participant communicates about their RM state 
    transitions, and (2) the $a$ transition was possible but intentionally just not taken.

!!! tip inline end "On the origin of the *CERT/CC Addendum* field in CERT/CC Vulnerability Notes"

    The problem described at left is why the individual Vendor records in
    CERT/CC Vulnerability Notes contain a *CERT/CC Addendum* field.

These last two imply some capacity for independent validation of
reports, which, on the surface, seems poised to add cost or complexity
to the process. However, in any MPCVD case with three or more Participants, a
consensus or voting heuristic could be applied. For example, should a
quorum of Participants agree that a Vendor's products are affected even
if the Vendor denies it, an opportunity exists to capture this
information as part of the case.

## A Reward Function for Minimizing EM Strings

Similarly, the EM process also has the potential to generate arbitrarily long histories,
as shown in [A Regular Grammar for EM](../process_models/em/index.md#sec:em_grammar).
Again, reliance on humans to resolve this shortcoming may be acceptable for now;
however, looking to the future, we can imagine a reward function to be optimized.
The EM reward function might include the following:

- a preference for short paths

- a preference for quick agreement (i.e., the $a$ transition appearing
    early in the EM
    history)

- a limit on how long an EM history can get without reaching
    $q^{em} \in A$ at all (i.e., How many proposal-rejection cycles are
    tolerable before giving up?)
