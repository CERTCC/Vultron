# Vulnerability Response Situation Awareness

{% include-markdown "../../includes/not_normative.md" %}

In this page, we demonstrate how the model can be applied to improve
situation awareness for coordinating parties and other stakeholders.

!!! ssvc "Situation Awareness and Vulnerability Response Decisions"

    Vulnerability prioritization schemes such as [SSVC](https://certcc.github.io/SSVC){:target="_blank"}
    generally give increased priority to states in higher
    threat levels, corresponding to $q \in \cdot \cdot \cdot \cdot X \cdot \cup \cdot \cdot \cdot \cdot \cdot A$. SSVC also includes decision
    points surrounding other states in our model. A summary of the relevant
    SSVC decision points and their intersection with our model is given in
    our [SSVC Crosswalk](../../reference/ssvc_crosswalk.md).

## Addressing Uncertainty in Situation Awareness

It is possible to use the case state model to infer what other decisions
can be made based on incomplete information about a case. For example, imagine
that a vendor just found out about a vulnerability in a product and has
taken no action yet. We know they are in ${Vf\cdot\cdot\cdot\cdot}$, but that
leaves 8 possible states for the case to be in:

!!! info "Possible states for a case in ${Vf\cdot\cdot\cdot\cdot}$"

    $$
    \begin{aligned}
        {Vf\cdot\cdot\cdot\cdot} = \{ & {Vfdpxa}, {VfdPxa}, {VfdpXa}, \\ 
                  & {VfdpxA}, {VfdPXa}, {VfdpXA}, \\
                  & {VfdPxA}, {VfdPXA} \}
    \end{aligned}
    $$

!!! question "Can we do better than simply assigning equal likelihood $p(q|Vf\cdot\cdot\cdot\cdot) = 0.125$ to each of these states?"

    Yes, we can use
    our [PageRank computations](../measuring_cvd/random_walk.md) to inform our estimates.

!!! example "Assessing the likelihood of states in ${Vf\cdot\cdot\cdot\cdot}$"

    To assess our presence in ${Vf\cdot\cdot\cdot\cdot}$, we can select just the
    subset of states we are interested in. But our PageRank values are computed across
    all 32 states and we are only interested in the relative probabilities
    within a subset of 8 states. Thus, we normalize the PageRank for the
    subset to find the results shown in the table below.
    
    | State     | PageRank | Normalized |
    |-----------|----------|------------|
    | $VfdPXA$  | 0.063    | 0.245      |
    | $VfdPXa$  | 0.051    | 0.200      |
    | $VfdPxa$  | 0.037    | 0.146      |
    | $VfdPxA$  | 0.032    | 0.126      |
    | $Vfdpxa$  | 0.031    | 0.120      |
    | $VfdpxA$  | 0.020    | 0.078      |  
    | $VfdpXa$  | 0.011    | 0.044      |
    | $VfdpXA$  | 0.010    | 0.040      |
     
    As a result, we find that the most likely state in ${Vf\cdot\cdot\cdot\cdot}$
    (given no other information) is ${VfdPXA}$ with probability $0.245$,
    nearly twice what we would have expected ($1/8 =
    0.125$) if we just assumed each state was equally probable.

!!! tip "Interpretation"

    One interpretation of the preceding example is that, barring evidence to 
    the contrary, the vendor might default to the following assumptions:

    - that the vulnerability is already public
    $p(P|Vf\cdot\cdot\cdot\cdot) = 0.245 + 0.200 + 0.146 + 0.126 = 0.717$
    - that an exploit is already publicly available 
    $p(X|Vf\cdot\cdot\cdot\cdot) = 0.245 + 0.200 + 0.044 + 0.040 = 0.529$
    - that attacks are occurring 
    $p(A|Vf\cdot\cdot\cdot\cdot) = 0.245 + 0.126 + 0.078 + 0.040 = 0.489$

    In other words, the vendor has a lot to gain by confirming that none of
    these assumptions are true as early as possible.
