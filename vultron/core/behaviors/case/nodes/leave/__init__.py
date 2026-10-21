#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""Action nodes for Leave(VulnerabilityCase) processing.

Implements the role-discriminating effects of a received Leave activity, split
by semantic concern (BTND-07-004):

- :mod:`.advance` — :class:`AdvanceParticipantToRMClosedNode` and
  :class:`AdvanceCaseActorToRMClosedNode`, which write ``RM.CLOSED`` to the
  *local* store.  The first is used on both the owner and non-owner paths (the
  departure effect is the same; what differs is whether the whole case also
  closes); the second is reached only on the owner path (CM-23-002 step 2).

- :mod:`.record` — :class:`CommitRMClosureEntriesNode`, which records each
  closure step an advance node wrote, for the leaving actor or for the
  CASE_MANAGER itself, as a canonical ``add_participant_status_to_participant``
  ledger entry and fans it out, so the replicas apply the steps rather than
  derive them (CM-23-001, CM-23-005).

- :mod:`.settle` — :class:`ExpirePendingInvitesOnCloseNode`, which expires
  every embargo Invite still awaiting a reply before the CASE_MANAGER's own
  closure, whose ``RM.CLOSED`` status entry is the write boundary (CM-23-014).

- :mod:`.decline` — :class:`EmitRejectCloseCaseNode`, the ``as:Reject`` arm for
  an owner close blocked by a live embargo (CM-23-011), and the optional reply
  to a Leave that arrives after the case is fully closed (CM-23-013).

- :mod:`.refuse` — :class:`RefuseOwnerLeaveWhileEmbargoedNode`, the sender-side
  refusal of the Case Owner's own ``leave-case`` call while its replica records
  an embargo in force (TRIG-13-003).  It is the only node here that runs on the
  leaving actor, not the CASE_MANAGER.

Re-exported here so existing importers keep working unchanged.

Per ADR-0050, ADR-0051, and specs/case-management.yaml CM-23-002/CM-23-003.
"""

from vultron.core.behaviors.case.nodes.leave.advance import (
    AdvanceCaseActorToRMClosedNode,
    AdvanceParticipantToRMClosedNode,
)
from vultron.core.behaviors.case.nodes.leave.decline import (
    LATE_LEAVE_DECLINE,
    EmitRejectCloseCaseNode,
)
from vultron.core.behaviors.case.nodes.leave.record import (
    CommitRMClosureEntriesNode,
)
from vultron.core.behaviors.case.nodes.leave.refuse import (
    RefuseOwnerLeaveWhileEmbargoedNode,
)
from vultron.core.behaviors.case.nodes.leave.settle import (
    ExpirePendingInvitesOnCloseNode,
)

__all__ = [
    "AdvanceCaseActorToRMClosedNode",
    "AdvanceParticipantToRMClosedNode",
    "CommitRMClosureEntriesNode",
    "EmitRejectCloseCaseNode",
    "ExpirePendingInvitesOnCloseNode",
    "LATE_LEAVE_DECLINE",
    "RefuseOwnerLeaveWhileEmbargoedNode",
]
