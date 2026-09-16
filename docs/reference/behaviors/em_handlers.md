# Embargo Management Behavior Trees

Auto-generated reference documentation for the Embargo Management (EM) behavior trees
in `vultron/core/behaviors/embargo/`.

## Requirements

The behavioral requirements for these trees are specified in the
[Protocol Specifications](../specs/protocol.md):

- [EMB-01](../specs/protocol.md#emb-01) — Receive EP (Embargo Proposal)
- [EMB-02](../specs/protocol.md#emb-02) — Receive EA (Embargo Acceptance)
- [EMB-03](../specs/protocol.md#emb-03) — Receive EJ (Embargo Rejection)
- [EMB-04](../specs/protocol.md#emb-04) — Receive EV (Embargo Revision)
- [EMB-05](../specs/protocol.md#emb-05) — Receive EC (Embargo Counter-proposal)
- [EMB-06](../specs/protocol.md#emb-06) — Receive ET (Embargo Teardown)
- [EMB-14](../specs/protocol.md#emb-14) — EM Write-Boundary Transition Validation

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
