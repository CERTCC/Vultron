# Report Prioritization Behavior

The Report Prioritization Behavior Tree is shown in the figure below.
It bears some structural similarity to the Report Validation Behavior Tree just described: An initial
post-condition check (A) falls back to the main process (B) leading toward
$accept$, which, in turn, falls back to the deferral process (C). 

In more detail, (A) if the report is already in either the *Accepted* or *Deferred* states and no
new information is available to prompt a change, the behavior ends.

```mermaid
---
title: Report Prioritization Behavior Tree
---
flowchart LR
    fb["?"]
    seq1["&rarr;"]
    fb -->|A| seq1
    rm_d_or_a(["RM in D or A?"])
    seq1 --> rm_d_or_a
    seq1fb["?"]
    seq1 --> seq1fb
    enough_info(["enough info?"])
    seq1fb --> enough_info
    gather_seq["&rarr;"]
    seq1fb --> gather_seq
    gather_info["gather info"]
    gather_seq --> gather_info
    no_info["no new info"]
    gather_seq --> no_info
    seq2["&rarr;"]
    fb -->|B| seq2
    rm_v_d_a(["RM in V, D, or A?"])
    seq2 --> rm_v_d_a
    eval_priority["evaluate priority"]
    seq2 --> eval_priority
    priority_not_defer(["priority is not defer?"])
    seq2 --> priority_not_defer
    accept_fb["?"]
    seq2 --> accept_fb
    rm_a(["RM in A?"])
    accept_fb --> rm_a
    accept_seq["&rarr;"]
    accept_fb --> accept_seq
    accept["accept"]
    accept_seq --> accept
    accept_to_a["RM &rarr; A<br/>(emit RA)"]
    accept_seq --> accept_to_a
    defer_fb["?"]
    fb -->|C| defer_fb
    rm_d(["RM in D?"])
    defer_fb --> rm_d
    defer_seq["&rarr;"]
    defer_fb --> defer_seq
    defer["defer"]
    defer_seq --> defer
    defer_to_d["RM &rarr; D<br/>(emit RD)"]
    defer_seq --> defer_to_d
```


Failing that, we enter the main prioritization sequence (B). The
preconditions of the main sequence are that either the report has not
yet been prioritized out of the *Valid* state ($q^{rm} \in V$) or new
information has been made available to a report in either
$q^{rm} \in \{ D, A \}$ to trigger a reevaluation.

Assuming the preconditions are met, the report priority is evaluated.
For example, a Participant using [SSVC](https://github.com/CERTCC/SSVC) could insert
that process here. The evaluation task is expected to always set the
report priority. The subsequent check returns *Failure* on a defer
priority or *Success* on any non-deferral priority. On *Success*, an
*accept* task is included as a placeholder for any intake process that a
Participant might have for *Accepted* reports. Assuming that it
succeeds, the report is explicitly moved to the *Accepted*
($q^{rm} \xrightarrow{a} A$) state, and an $RA$ message is emitted.

(C) Should any item in the main sequence fail, the case is deferred, its
state set to $q^{rm} \xrightarrow{d} D$, and an $RD$ message is emitted
accordingly. Similarly, a *defer* task is included as a callback
placeholder.
