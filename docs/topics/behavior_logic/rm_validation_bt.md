# Report Validation Behavior

A Report Validation Behavior Tree is shown in the next figure. To begin with, if the report is already
*Valid*, no further action is needed from this behavior.

```mermaid
---
title: Report Validation Behavior Tree
---
flowchart LR
    fb["?"]
    check_valid(["RM in V?"])
    fb --> check_valid
    i_seq["&rarr;"]
    fb --> i_seq
    check_invalid(["RM in I?"])
    i_seq --> check_invalid
    i_fb["?"]
    i_seq --> i_fb
    i_enough(["enough info?"])
    i_fb --> i_enough
    i_seq_seq["&rarr;"]
    i_fb --> i_seq_seq
    i_gather_info["gather info"]
    i_seq_seq --> i_gather_info
    i_no_info["no new info"]
    i_seq_seq --> i_no_info
    ri_seq["&rarr;"]
    fb --> ri_seq
    check_ri(["RM in R or I?"])
    ri_seq --> check_ri
    eval_cred["evaluate credibility"]
    ri_seq --> eval_cred
    eval_valid["evaluate validity"]
    ri_seq --> eval_valid
    ri_to_v["RM &rarr; V<br/>(emit RV)"]
    ri_seq --> ri_to_v
    ri_to_i["RM &rarr; I<br/>(emit RI)"]
    fb --> ri_to_i
```

When the report has already been designated as *Invalid*, the necessary
actions depend on whether further information is necessary, or not. If
the current information available in the report is sufficient, no
further action is necessary and the entire behavior returns *Success*.
However, a previous validation pass might have left some indicator that
more information was needed. In that case, execution proceeds to the
sequence in which the *gather info* task runs. If nothing new is found,
the entire branch returns *Success*, and the report remains *Invalid*.
If new information *is* found, though, the branch fails, driving
execution over to the main validation sequence.

The main validation sequence follows when none of the above conditions
have been met. In other words, the validation sequence is triggered when
the report is in *Received* and its validity has never been evaluated or
when the report was originally determined to be *Invalid* but new
information is available to prompt reconsideration. The validation
process shown here is comprised of two main steps: a credibility check
followed by a validity check as outlined in our introduction of 
the [Received (R) state]((../process_models/rm#the-received-r-state).

As a reminder, a report might be in one of three categories: (a) neither
credible nor valid, (b) credible but invalid, or (c) both credible and
valid. Assuming the report passes both the credibility and validity
checks, it is deemed *Valid*, moved to $q^{rm} \xrightarrow{v} V$, and
an $RV$ message is emitted.

Should either check fail, the validation sequence fails, the report is
deemed *Invalid* and moves (or remains in) $q^{rm} \in I$. In that case,
an $RI$ message is sent when appropriate to update other Participants on
the corresponding state change.
