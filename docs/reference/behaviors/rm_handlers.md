---
stakeholder_type: [project-contributor]
---

# Report Management Behavior Trees

Auto-generated reference documentation for the Report Management (RM) behavior trees
in `vultron/core/behaviors/report/`.

## Requirements

The behavioral requirements for these trees are specified in the
[Requirements Catalog](../vultron-spec/requirements/index.md):

- [RMB-01](../vultron-spec/requirements/state-behavior.md#protocol-rmb-01) — Receive RS (Report Submission)
- [RMB-09](../vultron-spec/requirements/state-behavior.md#protocol-rmb-09) — Enter RM Received
- [RMB-10](../vultron-spec/requirements/state-behavior.md#protocol-rmb-10) — Enter RM Valid
- [RMB-11](../vultron-spec/requirements/state-behavior.md#protocol-rmb-11) — Enter RM Invalid
- [RMB-12](../vultron-spec/requirements/state-behavior.md#protocol-rmb-12) — Enter RM Deferred
- [RMB-13](../vultron-spec/requirements/state-behavior.md#protocol-rmb-13) — Enter RM Accepted
- [RMB-14](../vultron-spec/requirements/state-behavior.md#protocol-rmb-14) — Enter RM Closed
- [RMB-15](../specs/project.md#rmb-15) — RM Write-Boundary Transition Validation

## Report Received Tree

Handles an incoming report submission (RS message). Constructed from
`vultron.core.behaviors.report.received_report_trees.create_report_received_tree`.

```python exec="true" idprefix=""
import sys
from pathlib import Path
_repo = Path.cwd()
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

import py_trees
from vultron.core.models.events.report import CreateReportReceivedEvent
from vultron.core.behaviors.report.received_report_trees import create_report_received_tree

tree = create_report_received_tree(
    CreateReportReceivedEvent(activity_id="a1", actor_id="actor1")
)
print("```")
print(py_trees.display.unicode_tree(tree))
print("```")
```

## Validate Report Tree

Validates an incoming report. Constructed from
`vultron.core.behaviors.report.validate_tree.create_validate_report_subtree`.

```python exec="true" idprefix=""
import sys
from pathlib import Path
_repo = Path.cwd()
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

import py_trees
from vultron.core.behaviors.report.validate_tree import create_validate_report_subtree

tree = create_validate_report_subtree(
    report_id="report-1",
    offer_id="offer-1",
    sender_actor_id="actor-1",
)
print("```")
print(py_trees.display.unicode_tree(tree))
print("```")
```

## Prioritize Report Tree

Prioritizes (accepts or defers) a validated report. Constructed from
`vultron.core.behaviors.report.prioritize_tree.create_prioritize_subtree`.

```python exec="true" idprefix=""
import sys
from pathlib import Path
_repo = Path.cwd()
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

import py_trees
from vultron.core.behaviors.report.prioritize_tree import create_prioritize_subtree

tree = create_prioritize_subtree(
    case_id="urn:uuid:case-1",
    actor_id="urn:uuid:actor-1",
)
print("```")
print(py_trees.display.unicode_tree(tree))
print("```")
```

## Close Report Tree

Closes a report. Constructed from
`vultron.core.behaviors.report.close_report_tree.create_close_report_tree`.

```python exec="true" idprefix=""
import sys
from pathlib import Path
_repo = Path.cwd()
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

import py_trees
from vultron.core.behaviors.report.close_report_tree import create_close_report_tree

tree = create_close_report_tree(case_id="urn:uuid:case-1")
print("```")
print(py_trees.display.unicode_tree(tree))
print("```")
```
