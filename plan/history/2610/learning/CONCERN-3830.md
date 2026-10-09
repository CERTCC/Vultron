---
source: CONCERN-3830
timestamp: '2026-10-07T17:37:44.107660+00:00'
title: No architecture ratchet catches a received tree whose emit nodes lack a CASE_MANAGER
  or sender gate
type: learning
---

## Concern

A CASE_MANAGER role gate was added to received-side trees one at a time: `update_tree` and the engage broadcast (#3746), the AckReport echo (#2667), the suggest-actor trees and the Accept(Invite) tree (#3752, #3823), with the close-case decline arm still open (#3825).
Each was found by a manual sibling scan, and each scan found the next.
Nothing in `test/architecture/` failed when a new received tree put an emit node in its effect section without `create_case_manager_gated_tree` or a sender check.

Suggested direction: an AST or structural ratchet over the `*_tree*.py` factories that call `create_receive_activity_tree`, with an allowlist for addressee-gated trees.

Governing specs: BT-17-001, BTND-07-005, ARCH-18-001, PCR-08-010.

## Decision

The gate moves into the factory so a tree cannot omit it.
`create_receive_activity_tree` takes `manager_effects` (wrapped in the gate after the commit) and `replica_effects` (ungated).
Emit-capable nodes carry one marker, and the factory raises at construction when a marked node is in `replica_effects` without a named exemption.
The rule is role gate only: a sender check alone never passes, because it says nothing about whether the replica owns the case (#2667).
BT-17-008 was amended and `notes/bt-pitfalls.md` gained a section.

**Resolved**: 2026-10-07 — implementation tracked in #4299, #4300, #4301, #4302.
Docs PR: <https://github.com/CERTCC/Vultron/pull/4298>.
