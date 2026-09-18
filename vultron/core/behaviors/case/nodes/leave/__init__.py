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

"""Receiver-side action nodes for Leave(VulnerabilityCase) processing.

Implements the role-discriminating effects of a received Leave activity, split
by semantic concern (BTND-07-004):

- :mod:`.advance` — :class:`AdvanceParticipantToRMClosedNode` and
  :class:`AdvanceCaseActorToRMClosedNode`, which write ``RM.CLOSED`` to the
  *local* store.  The first is used on both the owner and non-owner paths (the
  departure effect is the same; what differs is whether the whole case also
  closes); the second is reached only on the owner path (CM-23-002 step 2).

- :mod:`.record` — :class:`CommitCaseActorRMClosedEntryNode`, which records the
  CASE_MANAGER's transition as a canonical
  ``add_participant_status_to_participant`` ledger entry and fans it out, so the
  replicas can observe it rather than infer it (CM-23-005).

- :mod:`.decline` — :class:`EmitRejectCloseCaseNode`, the ``as:Reject`` arm for
  an owner close blocked by a live embargo (CM-23-011).

Re-exported here so existing importers keep working unchanged.

Per ADR-0050, ADR-0051, and specs/case-management.yaml CM-23-002/CM-23-003.
"""

from vultron.core.behaviors.case.nodes.leave.advance import (  # noqa: F401
    AdvanceCaseActorToRMClosedNode,
    AdvanceParticipantToRMClosedNode,
)
from vultron.core.behaviors.case.nodes.leave.decline import (  # noqa: F401
    EmitRejectCloseCaseNode,
)
from vultron.core.behaviors.case.nodes.leave.record import (  # noqa: F401
    CommitCaseActorRMClosedEntryNode,
)

__all__ = [
    "AdvanceCaseActorToRMClosedNode",
    "AdvanceParticipantToRMClosedNode",
    "CommitCaseActorRMClosedEntryNode",
    "EmitRejectCloseCaseNode",
]
