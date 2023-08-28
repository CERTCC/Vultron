# Deployment Behavior {#sec:deployment_bt}

The Deployment Behavior Tree is shown in the figure below.
The goal of this behavior is either for (A) the case to reach the $q^{cs} \in D$ state or (B) for the Participant to be
comfortable with remaining in a *Deferred* deployment state.

```mermaid
---
title: Deployment Behavior Tree
---
flowchart LR
    fb["?"]
    cs_d(["$CS in D?"])
    fb -->|A| cs_d
    rm_d_seq["&rarr;"]
    fb -->|B| rm_d_seq
    rm_d(["RM in D"])
    rm_d_seq --> rm_d
    rm_d_no_new_info([no new info?])
    rm_d_seq --> rm_d_no_new_info
    dep_seq["&rarr;"]
    fb -->|C| dep_seq
    role_is_deployer(["role is deployer?"])
    dep_seq -->|C1| role_is_deployer
    dep_fb["?"]
    dep_seq -->|C2| dep_fb
    rm_in_d_or_a(["RM in D or A?"])
    dep_fb --> rm_in_d_or_a
    da_seq["&rarr;"]
    dep_fb --> da_seq
    prioritize_dep["prioritize deployment"]
    da_seq --> prioritize_dep
    da_not_deferred(["priority not deferred?"])
    da_seq --> da_not_deferred
    da_rm_to_a["RM &rarr; A<br/>(emit RA)"]
    da_seq --> da_rm_to_a
    da_rm_to_d["RM &rarr; D<br/>(emit RD)"]
    dep_fb --> da_rm_to_d
    dep_fb2["?"]
    dep_seq -->|C3| dep_fb2
    df2_rm_d(["RM in D?"])
    dep_fb2 --> df2_rm_d
    df2_cs_VFD(["CS in VFD...?"])
    dep_fb2 --> df2_cs_VFD
    dseq["&rarr;"]
    dep_fb2 --> dseq
    dsfb["?"]
    dseq --> dsfb
    role_is_vendor(["role is vendor?"])
    dsfb --> role_is_vendor
    dsfb_cs_dP(["CS in ..dP..?"])
    dsfb --> dsfb_cs_dP
    ds_cs_VFd(["CS in VFd...?"])
    dseq --> ds_cs_VFd
    ds_deploy_fix["deploy fix"]
    dseq --> ds_deploy_fix
    dseq_to_d["CS ..d... &rarr; ..D...<br/>(emit CD)"]
    dseq --> dseq_to_d
    mit_dep(["mitigations deployed?"])
    dep_fb2 --> mit_dep
    mseq["&rarr;"]
    dep_fb2 --> mseq
    m_mit_avail(["mitigations available?"])
    mseq --> m_mit_avail
    m_deploy_mit(["deploy mitigation"])
    mseq --> m_deploy_mit
    mon_seq["&rarr;"]
    fb -->|D| mon_seq
    mon_req(["monitoring required?"])
    mon_seq --> mon_req
    mon["monitor deployment"]
    mon_seq --> mon
```

Assuming neither of these conditions has been met, the main deployment sequence (C) falls to the Deployer role (C1).
It consists of two subprocesses: prioritize deployment and deploy.

The prioritize deployment behavior is shown in (C2) the fallback node in the center of the diagram.
The subgoal is for the deployment priority to be established, as indicated by the Deployer's RM state $q^{rm} \in \{D,A\}$.
For example, a Deployer might use the [SSVC Deployer Tree](https://github.com/CERTCC/SSVC) to decide whether (and when) 
to deploy a fix or mitigation.
If the deployment priority evaluation indicates further action is needed,

- the report management state is set to $q^{rm} \in A$
- an $RA$ message is emitted, and 
- the overall prioritization behavior succeeds

Otherwise, when the deployment is *Deferred*, it results in a transition to state $q^{rm} \in D$ and
emission of an $RD$ message.

(C3) The deploy behavior is shown in the second fallback node of the center sequence (C).
It short-circuits to *Success* if either the deployment is *Deferred* or has already occurred.
The main sequence can fire in two cases:

1.  when the Deployer is also the Vendor and a fix is ready
    ($q^{cs} \in F$)
2.  when the Deployer is not the Vendor but the fix is both ready and
    public ($q^{cs} \in P$ and $q^{cs} \in F$)

Assuming either of these conditions is met,

- the deploy fix task can run, 
- the case status is updated to $q^{cs} \in D$, and 
- $CD$ emits on *Success*

Should the deployment sequence fail for any reason, a fallback is possible if undeployed mitigations are available.

(D) Finally, returning to the top part of the tree, Participants might choose to monitor the deployment process should they 
have the need to.

