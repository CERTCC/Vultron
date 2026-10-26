---
stakeholder_type: [project-contributor]
---

# Report Prioritization Behavior

## Requirements

The [Protocol Specifications](../../reference/specs/protocol.md) give the behavioral requirements for this tree:

- [RMB-12](../../reference/specs/protocol.md#rmb-12) — Enter RM Deferred
- [RMB-13](../../reference/specs/protocol.md#rmb-13) — Enter RM Accepted

!!! note "Implementation approach"

    The behavior tree diagram below shows one conformant implementation of these requirements.
    Implementations do not have to use behavior trees.
    Any approach that satisfies the requirements above is conformant.

!!! note "Legacy design diagram"

    The diagram on this page shows the simulator-era design from `vultron/bt/`.
    It may not match the current implementation in `vultron/core/behaviors/`.
    See the [Behaviors Reference](../../reference/behaviors/index.md) for documentation generated from the current implementation.

The figure below shows the Report Prioritization Behavior Tree.
Its structure is similar to the Report Validation Behavior Tree.
An initial postcondition check (A) falls back to the main process (B), which leads toward $accept$.
The main process in turn falls back to the deferral process (C).

In more detail, (A) the behavior ends if the report is already in the *Accepted* or *Deferred* state and no new information prompts a change.

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

If check (A) fails, we enter the main prioritization sequence (B).
This sequence has two alternative preconditions.
Either the report has not yet left the *Valid* state through prioritization ($q^{rm} \in V$).
Or new information is available for a report in $q^{rm} \in \{ D, A \}$, and this information triggers a new evaluation.

If the preconditions are met, the Participant evaluates the report priority.
For example, a Participant that uses [SSVC](https://github.com/CERTCC/SSVC){:target="_blank"} could put that process here.
The evaluation task always sets the report priority.
The next check returns *Failure* on a defer priority or *Success* on any other priority.

On *Success*, the tree runs an *accept* task.
This task is a placeholder for any intake process that a Participant has for *Accepted* reports.
If the task succeeds, the tree moves the report to the *Accepted* state ($q^{rm} \xrightarrow{a} A$) and emits an $RA$ message.

(C) If any item in the main sequence fails, the tree defers the case.
It sets the state with $q^{rm} \xrightarrow{d} D$ and emits an $RD$ message.
A *defer* task is also present as a callback placeholder.
