---
stakeholder_type: [project-contributor]
---

# Embargo Management Behavior Trees

Auto-generated reference documentation for the Embargo Management (EM) behavior trees
in `vultron/core/behaviors/embargo/`.

## Requirements

The behavioral requirements for these trees are specified in the
[Requirements Catalog](../vultron-spec/requirements/index.md):

- [EMB-10](../vultron-spec/requirements/state-behavior.md#protocol-emb-10) — Enter EM Proposed
- [EMB-11](../vultron-spec/requirements/state-behavior.md#protocol-emb-11) — Enter EM Active
- [EMB-12](../vultron-spec/requirements/state-behavior.md#protocol-emb-12) — Enter EM Revise
- [EMB-13](../vultron-spec/requirements/state-behavior.md#protocol-emb-13) — Enter EM Exited
- [EMB-14](../vultron-spec/requirements/state-behavior.md#protocol-emb-14) — Actor-Voluntary Embargo Termination (Trigger Side)

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
