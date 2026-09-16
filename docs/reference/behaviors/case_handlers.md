# Case Behavior Trees

Auto-generated reference documentation for case management and case state (CS) behavior trees
in `vultron/core/behaviors/case/` and `vultron/core/behaviors/sync/`.

## Requirements

The behavioral requirements for these trees are specified in the
[Protocol Specifications](../specs/protocol.md):

- [CSB-01](../specs/protocol.md#csb-01) — Receive CP (Case Proposal)
- [CSB-02](../specs/protocol.md#csb-02) — Receive CA (Case Acceptance)
- [CSB-03](../specs/protocol.md#csb-03) — Receive CR (Case Rejection)
- [CSB-15](../specs/protocol.md#csb-15) — Trigger-Side VFD Role Preconditions

## Accept Case Proposal Tree

Handles acceptance of an incoming case proposal. Constructed from
`vultron.core.behaviors.case.accept_case_proposal_received_tree.create_accept_case_proposal_received_tree`.

```python exec="true" idprefix=""
import sys
from pathlib import Path
_repo = Path.cwd()
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

import py_trees
from vultron.core.behaviors.case.accept_case_proposal_received_tree import (
    create_accept_case_proposal_received_tree,
)

tree = create_accept_case_proposal_received_tree(
    report_id="urn:uuid:report-1",
    case_actor_id="urn:uuid:actor-1",
)
print("```")
print(py_trees.display.unicode_tree(tree))
print("```")
```

## Reject Case Proposal Tree

Handles rejection of an incoming case proposal. Constructed from
`vultron.core.behaviors.case.reject_case_proposal_received_tree.create_reject_case_proposal_received_tree`.

```python exec="true" idprefix=""
import sys
from pathlib import Path
_repo = Path.cwd()
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

import py_trees
from vultron.core.behaviors.case.reject_case_proposal_received_tree import (
    create_reject_case_proposal_received_tree,
)

tree = create_reject_case_proposal_received_tree(report_id="urn:uuid:report-1")
print("```")
print(py_trees.display.unicode_tree(tree))
print("```")
```

## Accept Invite Tree

Handles acceptance of a case invitation. Constructed from
`vultron.core.behaviors.case.accept_invite_tree.create_accept_invite_actor_to_case_tree`.

```python exec="true" idprefix=""
import sys
from pathlib import Path
_repo = Path.cwd()
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

import py_trees
from vultron.core.behaviors.case.accept_invite_tree import (
    create_accept_invite_actor_to_case_tree,
)

tree = create_accept_invite_actor_to_case_tree(
    case_id="urn:uuid:case-1",
    invitee_id="urn:uuid:actor-1",
)
print("```")
print(py_trees.display.unicode_tree(tree))
print("```")
```

## Commit Log Entry Tree

Commits a new entry to the case ledger and fans it out to participants. Constructed from
`vultron.core.behaviors.sync.commit_tree.create_commit_log_entry_tree`.

```python exec="true" idprefix=""
import sys
from pathlib import Path
_repo = Path.cwd()
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

import py_trees
from vultron.core.behaviors.sync.commit_tree import create_commit_log_entry_tree

tree = create_commit_log_entry_tree(
    case_id="urn:uuid:case-1",
    object_id="urn:uuid:obj-1",
    event_type="create",
)
print("```")
print(py_trees.display.unicode_tree(tree))
print("```")
```

## Announce Log Entry Tree

Processes an incoming log entry announcement from the case manager. Constructed from
`vultron.core.behaviors.sync.announce_tree.create_announce_log_entry_tree`.

```python exec="true" idprefix=""
import sys
from pathlib import Path
_repo = Path.cwd()
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

import py_trees
from vultron.core.behaviors.sync.announce_tree import create_announce_log_entry_tree

tree = create_announce_log_entry_tree()
print("```")
print(py_trees.display.unicode_tree(tree))
print("```")
```
