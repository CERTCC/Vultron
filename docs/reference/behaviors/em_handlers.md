---
stakeholder_type: [project-contributor]
---

# Embargo Management Behavior Trees

Auto-generated reference documentation for the Embargo Management (EM) behavior trees
in `vultron/core/behaviors/embargo/`.

## Requirements

The behavioral requirements for these trees are specified in the
[Protocol Specifications](../specs/protocol.md):

- [EMB-10](../specs/protocol.md#emb-10) — Enter EM Proposed
- [EMB-11](../specs/protocol.md#emb-11) — Enter EM Active
- [EMB-12](../specs/protocol.md#emb-12) — Enter EM Revise
- [EMB-13](../specs/protocol.md#emb-13) — Enter EM Exited
- [EMB-14](../specs/protocol.md#emb-14) — Actor-Voluntary Embargo Termination (Trigger Side)

## Manage Embargo Tree

The top-level trigger-side embargo management tree. Evaluates whether to propose,
accept, revise, or exit the current embargo. Constructed from
`vultron.core.behaviors.embargo.manage_embargo_tree.create_manage_embargo_tree`.

```python exec="true" idprefix=""
import sys
from pathlib import Path
_repo = Path.cwd()
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

import py_trees
from vultron.core.behaviors.embargo.manage_embargo_tree import create_manage_embargo_tree

tree = create_manage_embargo_tree(case_id="urn:uuid:case-1")
print("```")
print(py_trees.display.unicode_tree(tree))
print("```")
```
