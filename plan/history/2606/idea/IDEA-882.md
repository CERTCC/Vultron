---
source: IDEA-882
timestamp: '2026-06-10T17:32:48.561382+00:00'
title: Standardize BT node module organization across vultron/core/behaviors/
type: idea
---

## Motivation

The codebase has organically evolved to split behavior trees into two layers:
tree factory functions (composition/structure) and leaf node modules
(implementation/details). This pattern has been successfully proven in case/,
report/, and sync/ areas using nodes/ subpackages with semantic modules.
However, embargo/, note/, sender/, and status/ still use flat nodes.py files.
This inconsistency creates maintenance friction and code-smell risks — notably
status/nodes.py (1,281 lines, 17 classes) and embargo/nodes.py (920 lines, 13
classes) both exceed the 10-class threshold documented in AGENTS.md.
Standardizing across all areas would improve code clarity, reduce review
friction, and prevent duplicate method definitions silently shadowing logic.

## Rough Approach

1. **embargo/** — Convert nodes.py to nodes/ subpackage with semantic modules:
   validation.py, em_transitions.py, pec_management.py, broadcast.py,
   trigger.py. Merge existing trigger_nodes.py.
2. **status/** — Convert nodes.py to nodes/ subpackage with semantic modules:
   participant_status.py, case_status.py (separating two workflows).
3. **note/** — Convert nodes.py to nodes/ subpackage (size is manageable but
   should follow standard).
4. **sender/** — Audit and standardize if needed.
5. **Test mirroring** — Create test/core/behaviors/{embargo,status,note,sender}/nodes/
   with one test file per semantic module.
6. Re-export all public names in `nodes/__init__.py` to preserve existing imports.

## References

- Related implementation issues: #876, #877, #878, #879, #880, #881
- AGENTS.md pitfall: "Flat nodes.py with 10+ BT Classes Is a Code Smell"
- Related specs: specs/behavior-tree-node-design.yaml (BTND-07-001, BTND-07-002)
- Related notes: notes/bt-integration.md (BT-related pitfalls reference)

**Processed**: 2026-06-10 — The split is universal (not size-triggered): all
process areas under `vultron/core/behaviors/` SHOULD use a `nodes/` subpackage
regardless of current size (BTND-07-001 updated). BTND-07-003 added to
formalize the tree/node structural split requirement. AGENTS.md pitfall
updated to focus on 500-line file-size threshold (CS-18-002) rather than
class count. Implementation tracked in #876 (status), #877 (embargo, incl.
`trigger_nodes.py` merge), #878 (`case/nodes/participant.py` further split),
\#883 (note + sender combined).
Docs PR: [#884](https://github.com/CERTCC/Vultron/pull/884).
