---
source: NOTES-behavioral-conformance-specs--design-rationale
timestamp: '2026-10-12T23:47:24.458911+00:00'
title: 'Behavioral conformance specs: design rationale (delivered)'
type: note
---

Archived from `notes/behavioral-conformance-specs.md` by #4497 (notes sweep): the
design rationale for creating the RMB/EMB/CSB behavioral conformance layer. The
layer is delivered — `specs/rm-behavior.yaml`, `specs/em-behavior.yaml` and
`specs/cs-behavior.yaml` exist and carry `satisfies` links to VP. The conformance
levels (L1–L4) are published in
`docs/reference/vultron-spec/_conformance/_conformance-testing.md`.

---

## Problem Statement

A large part of the Vultron protocol's behavior logic is currently embodied in
the py_trees behavior trees in `vultron/core/behaviors/`, and described
(descriptively, without normative language) in `docs/topics/behavior_logic/`.
An independent implementor — one who wants to build a Vultron-compliant system
without using this codebase as a template — has no machine-readable,
normatively-phrased specification of what their system must *do* in response to
protocol events and state conditions.

The existing `specs/vultron-protocol-spec.yaml` (VP) captures *policy* ("what
must be true"), and `docs/reference/formal_protocol/transitions.md` captures
normative message-level rules, but neither is organized as Event-Condition-Action
(ECA) rules. The behavior logic docs are purely descriptive and explicitly
frame BTs as *one* implementation approach, not a requirement.

## Core Insight: SHOULD/MUST Are a Downselect on MAY

The existing `vultron/core/case_states/patterns/potential_actions.py` already
encodes a MAY table: given a 6-char CVD state pattern, what actions are
*permitted*. The behavioral conformance specs add the normative layer on top:
of the permitted actions, which ones are MUST, SHOULD, or SHOULD_NOT under
what triggering conditions.

## Conformance Level Framing

Three levels an independent implementor can achieve:

- **L1 — Syntax**: well-formed messages (covered by wire format specs)
- **L2 — Semantic**: correct state transitions per message (covered by VP +
  transitions.md)
- **L3 — Behavioral**: correct observable outputs — right messages emitted,
  right states reached, given (input state + received message/event). This is
  what the new RMB/EMB/CSB specs cover.

A fourth level (L4 — Process: correct internal decision structure, e.g.,
precondition before state write before effect) is enforceable only via a
reference implementation. Some process ordering also rises to L3 when the
sequence of outputs is itself observable. For example, CP-before-ET (when
public disclosure triggers embargo teardown) is now normatively specified in
CSB-12-001 as a MUST, not just an implementation convention.

## Why New Files, Not VP Extensions

VP's items are flat normative statements: "Participants MUST X." ECA rules have
a three-part shape (precondition + trigger + required response) that doesn't
compress cleanly into that pattern. Adding 50+ ECA rules to VP would mix two
structurally different item kinds in one file and make VP hard to navigate.

New files also allow independent versioning. VP is already v1.0.0; the
behavioral layer starts at v0.1.0 and can stabilize separately.

The relationship direction: RMB/EMB/CSB items carry
`relationships: [{rel_type: satisfies, spec_id: VP-XX-XXX}]` pointing to the
VP policy they implement. Reverse traversal is free via
`SpecRegistry.graph` (networkx DiGraph, use `.predecessors(vp_id)`).
