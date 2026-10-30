### 13.5 Conformance Testing Approach

Conformance is judged from outside the implementation.
A test supplies a sequence of messages and an input state, and checks the messages the implementation emits and the state it reaches.
It does not inspect internal structure.

Each test case is therefore a message-sequence scenario paired with the state outcome it expects.

Some capabilities that define a role are not protocol-observable at all.
Developing a fix, deploying a fix and publishing an advisory happen outside the protocol.
Conformance verifies the protocol messages that this work produces, not the work itself.

Conformance testing is organized in four **layers**, which describe what a test verifies.
Layers are orthogonal to the capability sets of [§13.2 Capability Sets](../conformance.md#132-capability-sets), which describe what an implementation provides (see the warning in [§13.1 Conformance Model Overview](../conformance.md#131-conformance-model-overview)):

| Layer | Verifies |
|---|---|
| L1 — Syntax | Messages are well-formed against the wire format ([§5 Encoding and Transport](../layers.md#5-encoding-and-transport-n)) |
| L2 — Semantics | Each message drives the correct state transition ([§4 Messages](../layers.md#4-messages-n), [§6 Report Management (RM) State Machine](../tracking-models.md#6-report-management-rm-state-machine-n) through [§12 Participant Lifecycle Within a Case](../interactions.md#12-participant-lifecycle-within-a-case-n)) |
| L3 — Behavior | Correct observable outputs: right messages emitted and states reached, given input state plus received message |
| L4 — Process | Correct internal decision structure (e.g. precondition before state write before side-effect) |

L4 is only enforceable against a reference implementation and is therefore outside the scope of independent conformance claims.
Some process ordering surfaces at L3 where the output sequence is itself observable — the canonical-write-before-side-effects rule of [§11.3 Status Adoption: One Authorization Gate](../interactions.md#113-status-adoption-one-authorization-gate) being the clearest case.

!!! info "See also"
    - [Process Models](../../../topics/process_models/index.md) — the behavioral material the L2 and L3 layers test against

### 13.6 Capability Shapes

Capability shapes describe optional, pluggable capabilities that an implementation can connect to its own decision points.
They are not part of the Case Observer, Case Decision or Case Hosting capability sets, and a conformance claim does not state which shapes an implementation provides.

A capability shape is a contract between an implementation and the capability it connects, not a protocol rule: other participants cannot observe which shapes an implementation uses.
An implementation that provides a shape keeps to that shape's contract.
The shapes and their contracts are described in [Annex G Capability Shapes](../annex-g-capability-shapes.md#annex-g-capability-shapes-i).
