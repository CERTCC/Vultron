# Report Management Behavior Tree {#sec:rm_bt}

A Behavior Tree for the Report Management model is shown in the figure below.
The Report Management process is represented by a Fallback node. Note
that we assume that completing the process will require multiple *ticks*
of the Behavior Tree since each tick can complete, at most, only one
branch.

```mermaid
---
title: Report Management Behavior Tree
---
flowchart LR
    fb["?"]
    check_closed(["RM in C?"])
    fb -->|A| check_closed
    r_seq["&rarr;"]
    fb -->|B| r_seq
    check_received(["RM in R?"])
    r_seq --> check_received
    r_seq --> validate
    i_seq["&rarr;"]
    fb -->|C| i_seq
    check_invalid(["RM in I?"])
    i_seq --> check_invalid
    i_fb["?"]
    i_seq --> i_fb
    i_close["close"]
    i_fb --> i_close
    i_validate["validate"]
    i_fb --> i_validate
    v_seq["&rarr;"]
    fb -->|D| v_seq
    check_valid(["RM in V?"])
    v_seq --> check_valid
    v_prioritize[prioritize]
    v_seq --> v_prioritize
    d_seq["&rarr;"]
    fb -->|E| d_seq
    check_deferred(["RM in D?"])
    d_seq --> check_deferred
    d_fb["?"]
    d_seq --> d_fb
    d_close["close"]
    d_fb --> d_close
    d_prioritize["prioritize"]
    d_fb --> d_prioritize
    a_seq["&rarr;"]
    fb -->|F| a_seq
    check_accepted(["RM in A?"])
    a_seq --> check_accepted
    a_fb["?"]
    a_seq --> a_fb
    a_close["close"]
    a_fb --> a_close
    a_fb_seq["&rarr;"]
    a_fb --> a_fb_seq
    a_prioritize["prioritize"]
    a_fb_seq --> a_prioritize
    a__do_work["do work"]
    a_fb_seq --> a__do_work
```

(A) The first check is to see whether the case is already $Closed$
($q^{rm} \in C$). If that check succeeds, the branch returns *Success*,
and we're done. If it doesn't, we move on to the next branch (B), which
addresses reports in the *Received* state ($q^{rm} \in R$).

!!! tip inline end "See also"

    - [Report Validation Behavior](rm_validation_bt.md)
    - [Report Prioritization Behavior](rm_prioritization_bt.md)
    - [Report Closure Behavior](rm_closure_bt.md)
    - [Do Work Behavior](do_work_bt.md)

The only action to be taken from $q^{rm} \in R$ is to validate the report.
We address [report validation](rm_validation_bt.md) shortly, but, for now, it is
sufficient to say that the validate report behavior returns *Success* 
after moving the report to either *Valid* ($q^{rm} \xrightarrow{v} V$)
or *Invalid* ($q^{rm} \xrightarrow{i} I$).

The next branch (C) covers reports in the *Invalid* state ($q^{rm} \in I$).
Here we have two options: either close the report (move to
$q^{rm} \xrightarrow{c} C$, as described in [report closure](rm_closure_bt.md), or retry the validation.

(D) For reports that have reached the *Valid* state ($q^{rm} \in V$), our
only action is to prioritize the report. [Report prioritization](rm_prioritization_bt.md) is
addressed in detail elsewhere, but returns *Success* after moving the report to either *Accepted*
($q^{rm} \xrightarrow{a} A$) or *Deferred* ($q^{rm} \xrightarrow{d} D$).

(E) Next, we reach behaviors associated with reports that have been both validated
and prioritized. *Deferred* reports ($q^{rm} \in D$) can be *Closed* or
have their priority reevaluated, but otherwise are not expected to
receive additional work.

(F) Similarly, *Accepted* reports ($q^{rm} \in A$) can also be *Closed* or
have their priority reevaluated. However, they are also expected to
receive more effort---the *do work* task node, which we explore further
in [Do Work Behaviors](do_work_bt.md).
We are taking advantage of the composability of Behavior Trees to
simplify the presentation. Behaviors that appear in multiple places can
be represented as their own trees. We explore the most relevant of these
subtrees in the next few subsections.

