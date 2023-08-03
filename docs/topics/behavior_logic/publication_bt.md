# Publication Behavior

The Publication Behavior Tree is shown in the following diagram.
It begins by ensuring that the Participant knows what they intend to publish, followed by a check to
see if that publication has been achieved.
Assuming that work remains to be done, the main publish sequence commences on the second branch.

```mermaid
---
title: Publication Behavior Tree
---
flowchart LR
    fb["?"]
    seq1["&rarr;"]
    fb --> seq1
    fb2["?"]
    seq1 --> fb2
    pub_intents(["publication intents set?"])
    fb2 --> pub_intents
    prioritize_pub["prioritize publication intents"]
    fb2 --> prioritize_pub
    all_pub["all published?"]
    seq1 --> all_pub
    seq2["&rarr;"]
    fb --> seq2
    prep_pub["prepare publication"]
    seq2 --> prep_pub
    emb_mgt["embargo management"]
    seq2 --> emb_mgt
    em_n_or_x(["EM in N or X?"])
    seq2 --> em_n_or_x
    publish["publish"]
    seq2 --> publish
    cs_to_P["CS &rarr; P<br/>(emit CP)"]
    seq2 --> cs_to_P
```

!!! tip inline end "Embargoes and Publication"

    The [embargo management](/topics/behavior_logic/em_bt/) task here is intended as a simple check to ensure that no
    embargo remains active prior to publication.
    However, since we describe that behavior [elsewhere](/topics/behavior_logic/em_bt/), we will not repeat it here.
    Note that the [EM](/topics/process_models/em/) process may result in [early termination](/topics/process_models/em/early_termination/) of an existing embargo 
    if the Participant has sufficient cause to do so.

The publication process begins with [preparation for publication](#prepare-publication-behavior),
described below, followed by a pre-publication embargo check.

Once these subprocesses complete, the publish task fires, the case state
is updated to $q^{cs} \in P$, and a $CP$ message emits.

## Prepare Publication Behavior

The Prepare Publication Behavior Tree is shown in Figure
[\[fig:bt_prepare_publication\]](#fig:bt_prepare_publication){reference-type="ref"
reference="fig:bt_prepare_publication"}. There are separate branches for
publishing exploits, fixes, and reports. The publish exploit branch
succeeds if either no exploit publication is intended, if it is intended
and ready, or if it can be acquired and prepared for publication. The
publish fix branch succeeds if the Participant does not intend to
publish a fix (e.g., if they are not the Vendor), if a fix is ready, or
if it can be developed and prepared for publication. The publish report
branch is the simplest and succeeds if either no publication is intended
or if the report is ready to go.

Once all three branches have completed, the behavior returns *Success*.

