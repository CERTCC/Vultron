# Publication Behavior

The Publication Behavior Tree is shown in the following diagram.
(A) It begins by ensuring that the Participant knows what they intend to publish (A1), followed by a check to
see if that publication has been achieved (A2).
Assuming that work remains to be done, the main publish sequence commences on the second branch (B).

```mermaid
---
title: Publication Behavior Tree
---
flowchart LR
    fb["?"]
    seq1["&rarr;"]
    fb -->|A| seq1
    fb2["?"]
    seq1 -->|A1| fb2
    pub_intents(["publication intents set?"])
    fb2 --> pub_intents
    prioritize_pub["prioritize publication intents"]
    fb2 --> prioritize_pub
    all_pub["all published?"]
    seq1 -->|A2| all_pub
    seq2["&rarr;"]
    fb -->|B| seq2
    prep_pub["prepare publication"]
    seq2 -->|B1| prep_pub
    emb_mgt["embargo management"]
    seq2 -->|B2| emb_mgt
    em_n_or_x(["EM in N or X?"])
    seq2 -->|B3| em_n_or_x
    publish["publish"]
    seq2 -->|B4| publish
    cs_to_P["CS &rarr; P<br/>(emit CP)"]
    seq2 -->|B5| cs_to_P
```

!!! tip inline end "Embargoes and Publication"

    The [embargo management](em_bt.md) task here is intended as a simple check to ensure that no
    embargo remains active prior to publication.
    However, since we describe that behavior [elsewhere](em_bt.md), we will not repeat it here.
    Note that the [EM](../process_models/em/index.md) process may result in [early termination](../process_models/em/early_termination.md) of an existing embargo 
    if the Participant has sufficient cause to do so.

(B1) The publication process begins with [preparation for publication](#prepare-publication-behavior),
described below, followed by a pre-publication [embargo check](em_bt.md) (B2 and B3 combined).

Once these subprocesses complete, the publish task (B4) fires, the case state
is updated to $q^{cs} \in P$, and a $CP$ message emits (B5).

## Prepare Publication Behavior

The Prepare Publication Behavior Tree is shown below.
Note that it continues branch (B1) from the [Publication Behavior Tree](#publication-behavior) above.

```mermaid
---
title: Prepare Publication Behavior Tree
---
flowchart LR
    seq["&rarr;"]
    x_fb["?"]
    seq -->|B1a| x_fb
    no_pub_exploit(["no publish<br/>exploit?"])
    x_fb --> no_pub_exploit
    exp_ready(["exploit ready?"])
    x_fb --> exp_ready
    x_seq["&rarr;"]
    x_fb --> x_seq
    acquire_exploit["acquire exploit"]
    x_seq --> acquire_exploit
    prep_exploit["prepare exploit"]
    x_seq --> prep_exploit
    x_reprioritize["reprioritize exploit<br/>publication intent"]
    x_fb --> x_reprioritize
    f_fb["?"]
    seq -->|B1b| f_fb
    no_pub_fix(["no publish<br/>fix?"])
    f_fb --> no_pub_fix
    cs_in_VF(["CS in VF...?"])
    f_fb --> cs_in_VF
    f_seq["&rarr;"]
    f_fb --> f_seq
    fix_dev["fix development"]
    f_seq --> fix_dev
    prep_fix["prepare fix<br/>for publication"]
    f_seq --> prep_fix
    f_reprioritize["reprioritize fix<br/>publication intent"]
    f_fb --> f_reprioritize
    r_fb["?"]
    seq -->|B1c| r_fb
    no_pub_report(["no publish<br/>report?"])
    r_fb --> no_pub_report
    r_ready(["report ready?"])
    r_fb --> r_ready
    prep_report["prepare report<br/>for publication"]
    r_fb --> prep_report
    r_reprioritize["reprioritize report<br/>publication intent"]
    r_fb --> r_reprioritize
```

There are separate branches for
publishing exploits, fixes, and reports.

- (B1a) The publish exploit branch succeeds if either no exploit publication is intended, if it is [intended
  and ready](acquire_exploit_bt.md), or if it can be acquired and prepared for publication. 
- (B1b) The publish fix branch succeeds if the Participant does not intend to publish a fix (e.g., if they are not the Vendor), if a [fix is ready](fix_dev_bt.md), or
  if it can be developed and prepared for publication.
- (B1c) The publish report branch is the simplest and succeeds if either no publication is intended or if the report is ready to go.

Once all three branches have completed, the behavior returns *Success*.

