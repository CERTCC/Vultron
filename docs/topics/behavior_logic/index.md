---
stakeholder_type: [platform-developer, project-contributor]
level: 300
---

# Modeling an MPCVD AI Using Behavior Trees

These pages document the original Vultron Protocol behavior tree design for Multi-Party Coordinated Vulnerability Disclosure (MPCVD).
They are retained for two reasons.
They are the formal behavioral specification of what a Participant does at each step, and they record the design reasoning the protocol rests on.
They are not a walkthrough of the reference implementation, which realizes this design in `vultron/core/behaviors/`.

## Three views of the same behavior

We document behavior from three directions, and each direction answers a different question.

| View | Question it answers | Where |
|---|---|---|
| Original design | What behavior does the protocol call for, and why is it shaped this way? | [Original Behavior Tree Design](original_design.md) |
| Use-case behavior structure | For one coordination use case, what is decided mechanically, what is delegated outside the protocol, and what messages result? | [Use-Case Behavior](use-cases/index.md) |
| Current implementation | What trees does the reference implementation build today? | [Behaviors Reference](../../reference/behaviors/index.md) |

The design pages carry the intent.
The use-case pages give the shape of a single coordination step.
The reference pages give the tree the prototype actually runs.

All three views draw trees in the same notation.
If you have not read a behavior tree before, start with [Behavior Tree Notation](bt_notation.md): the node types, how a tree is read, and why behavior trees suit the protocol.

## Where judgment enters

Some task nodes on these design pages stand for a decision the protocol cannot make by itself — whether a report is credible, whether embargo terms are acceptable, whether an advisory is ready to publish.
Each of those is a **call-out point**: a location where an actor must obtain a judgment, a fact, or an artifact from outside the protocol ([ADR-0024](../../adr/0024-coordination-agent-taxonomy.md)).
The [Use-Case Behavior](use-cases/index.md) pages name the call-out points for each use case and say what decision each one represents.
The injection seam that lets a deployment answer a call-out point with a real service instead of a stub is recorded in [ADR-0025](../../adr/0025-call-out-point-abstraction-layer.md), and the service contracts are described in the [Capability Model](../capability_model/index.md).

---

!!! info "Normative requirements for the behaviors described here"

    The machine-readable behavioral conformance requirements underlying the trees in this section
    are located in the [Protocol Specifications](../../reference/specs/protocol.md):

    - [RMB — Report Management Behavioral Requirements](../../reference/specs/protocol.md#rmb)
    - [EMB — Embargo Management Behavioral Requirements](../../reference/specs/protocol.md#emb)
    - [CSB — CVD Case State Behavioral Requirements](../../reference/specs/protocol.md#csb)

    Each page in this section lists the relevant spec group IDs in its **Requirements** section.
    The behavior tree diagrams illustrate one conformant implementation; implementations are not
    required to use behavior trees.
