---
source: NOTES-triggers-test-coverage--structural-follow-up
timestamp: '2026-10-02T16:20:19.635801+00:00'
title: Structural follow-up
type: note
---

**Archived:** 2026-10-02
**Reason:** delivered — triggers/case.py split into triggers/case/ (#742 closed)
**Superseded by:** vultron/core/use_cases/triggers/case/

---

## Structural follow-up

The module structure of `triggers/case.py` mirrored the `nodes.py` smell that
[`specs/behavior-tree-node-design.yaml`](../specs/behavior-tree-node-design.yaml)
BTND-07-001 addresses for BT nodes: a flat module accumulating many classes
becomes high-blast-radius and review-hostile.

That follow-up has now landed: `triggers/case.py` was split into a
`triggers/case/` subpackage with one submodule per use case (issue #742).
