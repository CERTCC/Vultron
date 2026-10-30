---
source: CONCERN-5465
timestamp: '2026-10-29T20:49:37.043535+00:00'
title: A withheld teardown authorization leaves P beside an active embargo
type: learning
---

Theme: theme:requirements-traceability — decide how a withheld teardown authorization agrees with the CSB-18 invariants, so the protocol requirements do not contradict each other.

## Concern

Two sets of `protocol` requirements contradict each other when the Case Owner withholds teardown authorization.

- RSH-07-002 (relabeled `protocol` by #4899) says that, by default, the CASE_MANAGER gets the Case Owner's approval before it executes the embargo teardown that an adopted P, X or A value calls for. RSH-07-001 lets a Case Owner's own P report be adopted with no approval (RSH-07-006), so an adopted P can stand while the teardown waits.
- CSB-18-002, CSB-18-003 and CSB-18-004 say that a participant's composite state MUST NOT have P, X or A set while an embargo is active (EM `ACTIVE` or `REVISE`), because the P, X or A event causes the termination.

When the authorization is withheld, or not yet given, the case holds an adopted P beside an active embargo: the state that CSB-18 calls impossible. The reference implementation records this as a diagnostic note (`PxaEmInvariantDiagnosticNode`, #4829), and §11.3 of the Protocol Specification (`docs/reference/vultron-spec/_model-interactions.md`, "When teardown is required but not authorized") names it a contradiction. The YAML does not decide which rule gives way.

The receive rules CSB-04-007, CSB-05-008 and CSB-06-008 add to it: they say the CASE_MANAGER receiving CP, CX or CA "MUST initiate embargo termination by emitting ET", with no authorization step.

Found while reconciling the Interactions and Lifecycle page (#4899).

## Question

Which rule governs the window between adoption and an authorized teardown?

- **The invariant wins:** adopting P, X or A and terminating the embargo are one atomic step, so an adopted value needs the teardown's authorization too, and RSH-07-002 becomes part of RSH-07-001's adoption decision.
- **The authorization wins:** CSB-18-002 to CSB-18-004 are restated as invariants of a case whose teardown is authorized, and the window is a named, recorded state (the diagnostic note), not an impossible one. CSB-04-007, CSB-05-008 and CSB-06-008 then name the authorization step.

Governing specs: RSH-07-001, RSH-07-002, RSH-07-006, CSB-18-002, CSB-18-003, CSB-18-004, CSB-04-007, CSB-05-008, CSB-06-008

**Resolved**: 2026-10-29 — the invariant wins: adopting P, X or A and ending
the embargo are one authorized step (ADR-0166), and CSB-18-002 to CSB-18-004
are judged when a CASE_MANAGER act commits. Implementation tracked in #5511.

Docs PR: <https://github.com/CERTCC/Vultron/pull/5509>.
Notes: `notes/received-status-authorization.md`.
