### 12.5 Conformance Testing Approach

- Observable behavior is the test basis — not implementation internals
- Test cases are expressed as message-sequence scenarios with expected state
  outcomes
- Functional capabilities (develop fix, deploy fix, publish advisory) are
  role-defining but not directly protocol-observable; conformance is verified
  through the protocol messages they produce, not the work behind them

Conformance testing is organized in four **layers**, which describe what a test
verifies. These are orthogonal to the capability tiers of [§12.2](../index.md#122-capability-sets) (see the warning
in [§12.1](../index.md#121-conformance-model-overview)):

| Layer | Verifies |
|---|---|
| L1 — Syntax | Messages are well-formed against the wire format ([§5](../index.md#5-syntactic-layer-wire-format-n)) |
| L2 — Semantics | Each message drives the correct state transition ([§4](../index.md#4-semantic-layer-message-meanings-n), [§6](../index.md#6-report-management-rm-state-machine-n)–[§11](../index.md#11-participant-lifecycle-within-a-case-n)) |
| L3 — Behavior | Correct observable outputs: right messages emitted and states reached, given input state plus received message |
| L4 — Process | Correct internal decision structure (e.g. precondition before state write before side-effect) |

L4 is only enforceable against a reference implementation and is therefore
outside the scope of independent conformance claims. Some process ordering
surfaces at L3 where the output sequence is itself observable — the
canonical-write-before-side-effects rule of [§10.1](../index.md#101-status-adoption-the-two-seam-model) being the clearest case.

!!! info "See also"
    - `notes/behavioral-conformance-specs.md`
    - `specs/rm-behavior.yaml`, `specs/em-behavior.yaml`, `specs/cs-behavior.yaml`
