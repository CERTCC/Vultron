---
stakeholder_type: [project-contributor]
---

# Case State Behavior Trees

Auto-generated reference documentation for the Case State (CS) receive-side behavior trees
in `vultron/core/behaviors/status/`.

## Requirements

The behavioral requirements for these trees are specified in the
[Protocol Specifications](../specs/protocol.md):

- [RSH-01](../specs/protocol.md#rsh-01) — StatusAdoptionGate (participant status adoption)
- [RSH-02](../specs/project.md#rsh-02) — EmbargoTeardownAuthorizationGate
- [RSH-03](../specs/protocol.md#rsh-03) — ThreatTerminationBranchNode (embargo teardown)
- [RSH-04](../specs/protocol.md#rsh-04) — CaseStatus emission authority and outbound emit invariant
- [RSH-09](../specs/protocol.md#rsh-09) — Whole accept or reject of a received status
- [CSB-17](../specs/protocol.md#csb-17) — CS compound state and history validity
- [CSB-18](../specs/protocol.md#csb-18) — Cross-machine state entailments

## Add Case Status Tree

Handles receipt of an `Add(CaseStatus, VulnerabilityCase)` activity, which a participant replica admits from the case's CASE_MANAGER alone (RSH-04-005).
It runs the idempotency check, ephemeral-state guard, history-prefix guard and a whole accept-or-reject check of EM and P/X/A, and writes nothing: the replica takes the status from the ledger.
Constructed from
`vultron.core.behaviors.status.add_case_status_tree.add_case_status_tree`.

```python exec="true" idprefix=""
import sys
from pathlib import Path
_repo = Path.cwd()
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

import py_trees
from vultron.core.models.events.status import AddCaseStatusToCaseReceivedEvent
from vultron.core.behaviors.status.add_case_status_tree import add_case_status_tree
from vultron.core.use_cases.received.status import AddCaseStatusToCaseReceivedUseCase

tree = add_case_status_tree(
    AddCaseStatusToCaseReceivedEvent(activity_id="a1", actor_id="actor1"),
    sender_rule=AddCaseStatusToCaseReceivedUseCase.sender_entitlement,
)
print("```")
print(py_trees.display.unicode_tree(tree))
print("```")
```

## Add Participant Status Tree

Handles receipt of an `Add(ParticipantStatus, CaseParticipant)` activity.
Implements the StatusAdoptionGate workflow (ADR-0046, RSH-01): verifies the sender is a participant, appends the raw peer status, then gates adoption and optional embargo teardown through authorization call-outs.
An adopted P, X or A reaches the case status here, and nowhere else on the received side (RSH-01-003).
Constructed from
`vultron.core.behaviors.status.add_participant_status_tree.add_participant_status_tree`.

```python exec="true" idprefix=""
import sys
from pathlib import Path
_repo = Path.cwd()
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

import py_trees
from vultron.core.models.events.status import AddParticipantStatusToParticipantReceivedEvent
from vultron.core.behaviors.status.add_participant_status_tree import (
    add_participant_status_tree,
)
from vultron.core.use_cases.received.status import (
    AddParticipantStatusToParticipantReceivedUseCase,
)

tree = add_participant_status_tree(
    AddParticipantStatusToParticipantReceivedEvent(activity_id="a1", actor_id="actor1"),
    case_id="https://example.org/cases/case1",
    sender_rule=AddParticipantStatusToParticipantReceivedUseCase.sender_entitlement,
)
print("```")
print(py_trees.display.unicode_tree(tree))
print("```")
```
