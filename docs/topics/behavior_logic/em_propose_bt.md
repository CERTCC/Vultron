# Propose Embargo Behavior

The Propose Embargo Behavior Tree is shown in the figure below. 

```mermaid
---
title: Propose Embargo Behavior Tree
---
flowchart LR
    seq["&rarr;"]
    cs_pxa(["CS in ...pxa?"])
    seq --> cs_pxa
    fb1[?]
    seq --> fb1
    cs_d(["CS ..d...?"])
    fb1 --> cs_d
    other(["other reason"])
    fb1 --> other
    select["select terms"]
    seq --> select
    fb2[?]
    seq --> fb2
    pr_seq["&rarr;"]
    fb2 --> pr_seq
    em_p_or_r(["EM P or R?"])
    pr_seq --> em_p_or_r
    no_new_prop(["no new proposal?"])
    pr_seq --> no_new_prop
    np_seq["&rarr;"]
    fb2 --> np_seq
    em_n_or_p(["EM N or P?"])
    np_seq --> em_n_or_p
    em_to_p["EM &rarr; P<br/>(emit EP)"]
    np_seq --> em_to_p
    ar_seq["&rarr;"]
    fb1 --> ar_seq
    em_a_or_r(["EM A or R?"])
    ar_seq --> em_a_or_r
    em_to_r["EM &rarr; R<br/>(emit EV)"]
    ar_seq --> em_to_r
```

It consists of a sequence that begins with a check for embargo viability as outlined in
[Negotiating Embargoes](../process_models/em/negotiating/).
Once the checks succeed, it proceeds to selecting embargo terms to propose.
Implementations of this task might simply draw from a default policy, as in 
[Default Embargoes](../process_models/em/defaults.md), or it might be a case-specific decision made by a Participant.
Embargo terms can be proposed from any of the non-*eXited* states ($q^{em} \in \{N,P,A,R\}$).
If a new or revised embargo has already been proposed, the tree then checks whether a counterproposal is desired.
Assuming it is not, no proposal is made, and the behavior succeeds.
Otherwise, proposals from state $q^{em} \in N$ emit $EP$ and transition $q^{em} \xrightarrow{p} P$, 
whereas those from $q^{em} \in A$ emit $EV$ and move to $q^{em} \xrightarrow{p} R$.
Proposals from states $q^{em} \in P$ or $q^{em} \in R$ represent counterproposals and, therefore, do not change
the EM state.
They do, however, emit $EP$ or $EV$ messages as appropriate.

