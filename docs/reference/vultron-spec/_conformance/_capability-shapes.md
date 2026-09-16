### Annex G — Capability Shapes [I]

Capability shapes define optional, pluggable capabilities that connect to
call-out points in the behavior engine. Capability shapes and capability sets
([§12.2](../index.md#122-capability-sets)) are independent: an implementation may
provide the Observer capability set and no capability shapes at all.

A capability shape defines a **contract** — what the call-out point accepts and
what it returns. A concrete implementation that satisfies the contract is a
Vultron-compatible capability of that shape.

!!! note "Informative: why \"shape\""
    A shape is a contract, not a component and not an autonomous system. Any
    mechanism that satisfies the contract fits the shape: a human following a
    procedure, a script, a model, or a service.

#### G.1 The Five Capability Shapes

| Shape | Contract: accepts | Contract: returns | Notes |
|---|---|---|---|
| **Sentinel** | A condition to monitor | SUCCESS/FAILURE, no side effects | Operates on the call-in surface; has no call-out point node. Used as a precondition guard. |
| **Evaluator** | A situation and a set of options | A structured recommendation | Its result gates downstream execution. |
| **Retriever** | A query | Structured facts from an external source | — |
| **Composer** | Context | A new content artifact written to the blackboard | The discriminator vs. Actuator: if a content artifact lands on the blackboard, it is a Composer. |
| **Actuator** | A trigger | SUCCESS when the side effect is confirmed; FAILURE otherwise | Invokes an external system for a side effect. Produces no content artifact. |

!!! warning "Distinguishing Composer from Actuator"
    Both shapes call external systems. The discriminator is whether a content
    artifact is written to the blackboard. If the only output is a SUCCESS/FAILURE
    confirming an external side effect, the shape is **Actuator**, not Composer.

#### G.2 Relationship to Conformance

Capability shapes are not part of the Observer, Authority or Hosting capability
set requirements. An implementation at any capability set level may provide any
number of shapes, and a conformance claim does not state which
([§12.6](../index.md#126-capability-shapes)).

Where a capability shape is implemented, it MUST satisfy the contract defined
above. The technology used to fulfill the contract is not specified: a shape
may be fulfilled by a human, an automated script, an LLM, or any other mechanism.

#### G.3 Relationship to the Reference Implementation

In the Python reference implementation, a capability shape maps to a Port
(abstract Protocol interface) and a concrete capability maps to an Adapter.
This mapping is specific to the hexagonal architecture of the reference
implementation. Other implementations are not required to use this structure.

!!! info "See also"
    - ADR-0024 (original agent shape taxonomy)
    - ADR-0025 (call-out point abstraction)
    - `docs/reference/vultron-taxonomy.md`

---
