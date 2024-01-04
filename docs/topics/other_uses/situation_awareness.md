# Vulnerability Response Situation Awareness

{% include-markdown "../../includes/not_normative.md" %}

In this page, we demonstrate how the model can be applied to improve
situation awareness for coordinating parties and other stakeholders.

## SSVC v2.0

{== TODO merge with [SSVC crosswalk](../../reference/ssvc_crosswalk.md) ==}

Vulnerability prioritization schemes such as [SSVC](<https://github>.
com/CERTCC/SSVC) generally give increased priority to states in higher
threat levels, corresponding to $q \in \cdot \cdot \cdot \cdot X \cdot \cup \cdot \cdot \cdot \cdot \cdot A$. SSVC also includes decision
points surrounding other states in our model. A summary of the relevant
SSVC decision points and their intersection with our model is given in
the table below.

| States                            | SSVC Decision Point | SSVC Value |
|-----------------------------------|---------------------|------------|
| $\cdot \cdot \cdot \cdot xa$      | Exploitation        | None       |
| $\cdot \cdot \cdot \cdot Xa$      | Exploitation        | PoC        |
| $\cdot \cdot \cdot \cdot \cdot A$ | Exploitation        | Active     |
| $\cdot \cdot \cdot p\cdot \cdot$  | Report Public       | No         |
| $\cdot \cdot \cdot P\cdot \cdot$  | Report Public       | Yes        |
| $V\cdot \cdot \cdot \cdot \cdot$  | Supplier Contacted  | Yes        |
| $v\cdot \cdot \cdot \cdot \cdot$  | Supplier Contacted  | No         |
| $\cdot \cdot \cdot p\cdot \cdot$  | Public Value Added  | Precedence |
| $VFdp\cdot \cdot$                 | Public Value Added  | Ampliative |
| $\cdot \cdot dP\cdot \cdot$       | Public Value Added  | Ampliative |
| $VF\cdot P\cdot \cdot$            | Public Value Added  | Limited    |

Not all SSVC decision point values map as clearly onto states in this
model however. For example, *Supplier Contacted=No* likely means
$q \in v \cdot \cdot \cdot \cdot \cdot$ but it is possible that the vendor has
found out
another way, so one cannot rule out $q \in V \cdot \cdot \cdot \cdot \cdot$ on
this basis alone.
However, notifying the vendor yourself forces you into
$q \in  V \cdot \cdot \cdot \cdot \cdot$. Therefore it is always in the coordinator's
interest to encourage, facilitate, or otherwise cause the vendor to be
notified.

Other SSVC decision points may be informative about which transitions to
expect in a case. Two examples apply here: First, *Supplier Engagement*
acts to gauge the likelihood of the **F** transitions.
Coordination becomes more necessary the lower that likelihood is.
Second, *Utility* (the usefulness of the exploit to the adversary) acts
to gauge the likelihood of the **A** transition.

## Mapping to CVSS v3.1

{== TODO update to CVSS v4. ==}

{== TODO Consider making a crosswalk in reference section instead of here. ==}

[CVSS version 3.1](https://www.first.org/cvss/v3.1/specification-document)
includes a few Temporal Metric variables that connect to this model.
Unfortunately, differences in abstraction between the models leaves a good
deal of ambiguity in the translation. The table below shows the
relationship between the two models.

| States                         | CVSS v3.1 Temporal Metric | CVSS v3.1 Temporal Metric Value(s)                                     |
|--------------------------------|---------------------------|------------------------------------------------------------------------|
| $\cdot\cdot\cdot\cdot XA$      | Exploit Maturity          | High (H), or Functional (F)                                            |
| $\cdot\cdot\cdot\cdot X \cdot$ | Exploit Maturity          | High (H), Functional (F), or Proof-of-Concept (P)                      |
| $\cdot\cdot\cdot\cdot x \cdot$ | Exploit Maturity          | Unproven (U) or Not Defined (X)                                        |
| $Vf\cdot\cdot\cdot\cdot$       | Remediation Level         | Not Defined (X), Unavailable (U), Workaround (W), or Temporary Fix (T) |
| $VF\cdot\cdot\cdot\cdot$       | Remediation Level         | Temporary Fix (T) or Official Fix (O)                                  |

## Addressing Uncertainty in Situation Awareness

!!! info inline end "Possible states for a case in $
{Vf\cdot\cdot\cdot\cdot}$"

    $$\begin{aligned}
        {Vf\cdot\cdot\cdot\cdot} = \{ & {Vfdpxa}, {VfdPxa}, {VfdpXa}, \\ 
                  & {VfdpxA}, {VfdPXa}, {VfdpXA}, \\
                  & {VfdPxA}, {VfdPXA} \}
    \end{aligned}$$

It is possible to use the case state model to infer what other decisions
can be made based on incomplete information about a case. For example, imagine
that a vendor just found out about a vulnerability in a product and has
taken no action yet. We know they are in ${Vf\cdot\cdot\cdot\cdot}$, but that
leaves 8 possible states for the case to be in (shown at right).

Can we do better than simply assigning equal likelihood
$p(q|Vf\cdot\cdot\cdot\cdot) = 0.125$ to each of these states? Yes: we can use
the PageRank computations from [](../measuring_cvd/random_walk.md) to inform our estimates.

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

    One interpretation of this result is that, barring evidence to 
    the contrary, the vendor might default to the following assumptions:

    - that the vulnerability is already public
    $p(P|Vf\cdot\cdot\cdot\cdot) = 0.245 + 0.200 + 0.146 + 0.126 = 0.717$
    - that an exploit is already publicly available 
    $p(X|Vf\cdot\cdot\cdot\cdot) = 0.245 + 0.200 + 0.044 + 0.040 = 0.529$
    - that attacks are occurring 
    $p(A|Vf\cdot\cdot\cdot\cdot) = 0.245 + 0.126 + 0.078 + 0.040 = 0.489$

    In other words, the vendor has a lot to gain by confirming that none of
    these assumptions are true as early as possible.
