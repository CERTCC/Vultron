---
source: CONCERN-5855
timestamp: '2026-11-05T14:39:51.944576+00:00'
title: BTND-01-004 and BTND-10-005 disagree on where a BT node gets its case_id
type: learning
---

Theme: theme:requirements-traceability — the BT node design specs give one answer to where a node's case ID comes from.

## Summary

Three behavior-tree node design requirements give different answers to where a node gets its case ID:

- BTND-01-004 (MUST): a BT node MUST take each value that varies by usage site, a case ID included, as a constructor parameter.
- BTND-01-005 (MUST): a BT node MUST receive each variable input through a constructor parameter or the documented blackboard interface.
- BTND-10-005 (MUST): the ParticipantStatus write node MUST obtain `case_id` from its declared blackboard port, never from a constructor argument.

BTND-10-005 forbids what BTND-01-004 requires; BTND-01-005 permits both.

## Surface Symptom vs. Underlying Problem

Surface: a missing link. The SR-13 link audit (PR #5853, #5212) could have recorded BTND-10-005 `supersedes` BTND-01-004 and moved on.
Underlying: the specs do not say which rule governs, so a link would choose a design. Either the blackboard-port pattern is the exception (BTND-10-005 supersedes BTND-01-004 for that node), or it is the general rule and BTND-01-004 should be reworded to allow a declared port. BTND-01-005's either-way wording looks like the correct general rule and should stay.

## Category

Spec contradiction.

## Severity

Medium. An agent writing a new node can cite either MUST and be right.

## Evidence

- `specs/behavior-tree-node-design.yaml`: BTND-01-004, BTND-01-005, BTND-10-005.
- Recorded as an open question in PR #5853's body; no link was changed on its account.

## Impact if Ignored

New nodes split between the two patterns, and a reviewer cannot say which one is the defect.

## Suggested Action

Decide whether a case ID may come from a declared blackboard port in general. Then either reword BTND-01-004 to allow a declared port (and drop its case-ID example), or record BTND-10-005 `supersedes` BTND-01-004 and say in BTND-10-005 why that node is the exception.

**Resolved**: 2026-11-05 — decided as a spec rule; the code does not yet conform, tracked in #5907. A usage-site value that every tree using the node knows at build time is a constructor parameter (BTND-01-004, narrowed). A value some tree finds only at tick time comes from a declared blackboard input port in every tree (new BTND-01-006, refines BTND-01-005), never also from the constructor (new BTND-01-007). BTND-10-005 now refines BTND-01-006.
Docs PR: https://github.com/CERTCC/Vultron/pull/5902.
Spec: `specs/behavior-tree-node-design.yaml`.
