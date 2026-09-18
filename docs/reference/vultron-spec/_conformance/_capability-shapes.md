### Annex G — Capability Shapes [I]

Capability shapes define optional, pluggable capabilities that connect to
call-out points in the behavior engine. Capability shapes and capability sets
([§12.2](../index.md#122-capability-sets)) are independent: an implementation may
provide the Case Observer capability set and no capability shapes at all.

A capability shape defines a **contract** — what the call-out point accepts and
what it returns. A concrete implementation that satisfies the contract is a
Vultron-compatible capability of that shape.

!!! note "Informative: why \"shape\""
    A shape is a contract, not a component and not an autonomous system. Any
    mechanism that satisfies the contract fits the shape: a human following a
    procedure, a script, a model, or a service.

#### G.1 The Four Capability Shapes

Four shapes cover the ways an external capability can be consulted. They differ in
what they are given, what they return, and whether they change anything outside the
case. All four are consulted *by* the protocol, and each MUST answer within the
single tick that consults it.

| Shape | Contract: accepts | Contract: returns | Notes |
|---|---|---|---|
| **Evaluator** | A situation and a set of options | A structured recommendation | Its result gates downstream execution. |
| **Retriever** | A query | Structured facts from an external source | A boolean is the simplest structured fact; a yes/no external query is a Retriever. |
| **Composer** | Context | A new content artifact written to the blackboard | The discriminator vs. Actuator: if a content artifact lands on the blackboard, it is a Composer. |
| **Actuator** | A trigger | SUCCESS when the side effect is confirmed; FAILURE otherwise | Invokes an external system for a side effect. Produces no content artifact. |

!!! warning "Distinguishing Composer from Actuator"
    Both shapes call external systems. The discriminator is whether a content
    artifact is written to the blackboard. If the only output is a SUCCESS/FAILURE
    confirming an external side effect, the shape is **Actuator**, not Composer.

!!! note "Informative: the Sentinel pattern is not a capability shape"
    A **Sentinel** monitors a condition and acts when it fires. The protocol never
    consults it, so it answers no call-out point and has no contract of the kind
    tabled above — no accepted input, no returned value, no blackboard
    interaction. It is a **call-in** pattern, the reverse direction of every shape
    above.

    The discriminator is **who initiates**, not where the information comes from.
    A capability is consulted and answers within the tick that asks. A Sentinel
    decides for itself that the moment has come. A Sentinel may well be a case
    **Participant** — typically holding the **Observer** role — in which case it
    learns case state through ordinary ledger replication and acts by sending
    ordinary protocol messages, with both visible to every participant. It may
    equally be operator-side machinery with no case identity, driving one actor
    through its trigger endpoints and invisible to the case. That choice is a
    protocol-visibility decision.

    Two consequences for an implementer. A capability that answers a question the
    protocol asks is one of the four shapes, never a Sentinel — including one that
    answers only yes or no, which is a Retriever. And a Sentinel needs none of the
    capability-shape machinery: it needs a way to observe, a decision rule, and
    something to call.

#### G.2 Relationship to Conformance

Capability shapes are not part of the Case Observer, Case Decision or Case Hosting
capability set requirements. An implementation at any capability set level may provide any
number of shapes, and a conformance claim does not state which
([§12.6](../index.md#126-capability-shapes)).

Where a capability shape is implemented, it MUST satisfy the contract defined
above. The technology used to fulfill the contract is not specified: a shape
may be fulfilled by a human, an automated script, an LLM, or any other mechanism.

#### G.3 Relationship to the Reference Implementation

In the Python reference implementation the three taxonomy levels map onto three
distinct artifacts:

| Level | Reference-implementation artifact |
|---|---|
| Capability shape | A base class in the core behavior layer that fixes the lifecycle for that shape |
| Capability | A core-owned declaration naming the shape and the typed blackboard ports the capability reads and writes |
| Capability implementation | A factory callable satisfying the backend Protocol, injected through a domain bundle |

The contract a capability declares is machine-readable and belongs to the core
layer, so a substituted implementation is checked against it rather than trusted.
This mapping is specific to the hexagonal architecture of the reference
implementation. Other implementations are not required to use this structure.

!!! info "See also"
    - ADR-0024 (original shape taxonomy; the term "call-out point")
    - ADR-0025 (call-out point abstraction)
    - ADR-0097 (four shapes; core-declared contracts; Sentinel as a call-in pattern)
    - `docs/reference/vultron-taxonomy.md`

---
