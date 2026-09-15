### 12.5 Conformance Testing Approach

- Observable behavior is the test basis — not implementation internals
- Test cases are expressed as message-sequence scenarios with expected state
  outcomes
- Functional capabilities (develop fix, deploy fix, publish advisory) are
  role-defining but not directly protocol-observable; conformance is verified
  through the protocol messages they produce, not the work behind them

Conformance testing is organized in four **layers**, which describe what a test
verifies. These are orthogonal to the capability tiers of §12.2 (see the warning
in §12.1):

| Layer | Verifies |
|---|---|
| L1 — Syntax | Messages are well-formed against the wire format (§5) |
| L2 — Semantics | Each message drives the correct state transition (§4, §6–§11) |
| L3 — Behavior | Correct observable outputs: right messages emitted and states reached, given input state plus received message |
| L4 — Process | Correct internal decision structure (e.g. precondition before state write before side-effect) |

L4 is only enforceable against a reference implementation and is therefore
outside the scope of independent conformance claims. Some process ordering
surfaces at L3 where the output sequence is itself observable — the
canonical-write-before-side-effects rule of §10.1 being the clearest case.

!!! info "See also"
    - `notes/behavioral-conformance-specs.md`
    - `specs/rm-behavior.yaml`, `specs/em-behavior.yaml`, `specs/cs-behavior.yaml`
