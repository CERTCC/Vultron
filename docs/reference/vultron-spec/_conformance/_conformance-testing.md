### 12.5 Conformance Testing Approach

Conformance is judged from outside the implementation. A test supplies a sequence
of messages and an input state, and checks the messages the implementation emits
and the state it reaches. It does not inspect internal structure.

Each test case is therefore a message-sequence scenario paired with the state
outcome it expects.

Some capabilities that define a role are not protocol-observable at all.
Developing a fix, deploying a fix and publishing an advisory happen outside the
protocol. Conformance verifies the protocol messages that this work produces, not
the work itself.

Conformance testing is organized in four **layers**, which describe what a test
verifies. Layers are orthogonal to the capability sets of
[§12.2](../index.md#122-capability-sets), which describe what an implementation
provides (see the warning in [§12.1](../index.md#121-conformance-model-overview)):

| Layer | Verifies |
|---|---|
| L1 — Syntax | Messages are well-formed against the wire format ([§5](../index.md#5-syntactic-layer-wire-format-n)) |
| L2 — Semantics | Each message drives the correct state transition ([§4](../index.md#4-semantic-layer-message-meanings-n), [§6](../index.md#6-report-management-rm-state-machine-n)–[§11](../index.md#11-participant-lifecycle-within-a-case-n)) |
| L3 — Behavior | Correct observable outputs: right messages emitted and states reached, given input state plus received message |
| L4 — Process | Correct internal decision structure (e.g. precondition before state write before side-effect) |

L4 is only enforceable against a reference implementation and is therefore
outside the scope of independent conformance claims. Some process ordering
surfaces at L3 where the output sequence is itself observable — the
canonical-write-before-side-effects rule of [§10.3](../index.md#103-status-adoption-the-two-seam-model) being the clearest case.

!!! info "See also"
    - [Process Models](../../../topics/process_models/index.md) — the behavioral
      material the L2 and L3 layers test against
