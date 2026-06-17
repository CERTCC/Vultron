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

"""BT nodes subpackage for status-related workflows.

Re-exports all public node classes and constants from domain-specific
submodules so that existing import paths
(``from vultron.core.behaviors.status.nodes import ...``) continue to work
without modification.

Submodules:
- ``conditions``: Participant verification condition nodes
- ``broadcast``: Peer fan-out helper and nodes (_find_case_manager_id,
  FindCaseManagerNode, FilterPeerRecipientsNode,
  CreateStatusBroadcastActivityNode, BroadcastQueueToOutboxNode,
  BroadcastStatusToPeersNode)
- ``append``: Load, validate RM transition, and append action nodes
  (SkipIfIdempotentNode, LoadParticipantNode,
  CheckStatusNotAlreadyAppendedNode, ResolveAndPersistStatusObjectNode,
  ValidateRMTransitionNode, AppendStatusAndSaveParticipantNode)
- ``lifecycle``: Public disclosure and auto-close lifecycle nodes
  (_PublicDisclosureSkipConditionNode, PublicDisclosureBranchNode,
  AutoCloseBranchNode)
- ``case_status``: Idempotency guard, EM/PXA transition validation, and
  append nodes for the AddCaseStatusToCase workflow
"""

from vultron.core.behaviors.status.nodes.broadcast import (
    BroadcastQueueToOutboxNode,
    BroadcastStatusToPeersNode,
    CreateStatusBroadcastActivityNode,
    FilterPeerRecipientsNode,
    FindCaseManagerNode,
    _find_case_manager_id,
)
from vultron.core.behaviors.status.nodes.case_status import (
    CASE_STATUS_ALREADY_PRESENT,
    AppendCaseStatusToCaseNode,
    CheckCaseStatusIdempotencyNode,
    ValidateCaseStatusTransitionNode,
)
from vultron.core.behaviors.status.nodes.conditions import (
    VerifySenderIsParticipantNode,
)
from vultron.core.behaviors.status.nodes.append import (
    AppendStatusAndSaveParticipantNode,
    CheckStatusNotAlreadyAppendedNode,
    LoadParticipantNode,
    ResolveAndPersistStatusObjectNode,
    SkipIfIdempotentNode,
    ValidateRMTransitionNode,
)
from vultron.core.behaviors.status.nodes.lifecycle import (
    AutoCloseBranchNode,
    PublicDisclosureBranchNode,
    _PublicDisclosureSkipConditionNode,
)

__all__ = [
    # conditions
    "VerifySenderIsParticipantNode",
    # broadcast
    "_find_case_manager_id",
    "FindCaseManagerNode",
    "FilterPeerRecipientsNode",
    "CreateStatusBroadcastActivityNode",
    "BroadcastQueueToOutboxNode",
    "BroadcastStatusToPeersNode",
    # append
    "LoadParticipantNode",
    "CheckStatusNotAlreadyAppendedNode",
    "ResolveAndPersistStatusObjectNode",
    "ValidateRMTransitionNode",
    "AppendStatusAndSaveParticipantNode",
    "SkipIfIdempotentNode",
    # lifecycle
    "_PublicDisclosureSkipConditionNode",
    "PublicDisclosureBranchNode",
    "AutoCloseBranchNode",
    # case_status
    "CASE_STATUS_ALREADY_PRESENT",
    "CheckCaseStatusIdempotencyNode",
    "ValidateCaseStatusTransitionNode",
    "AppendCaseStatusToCaseNode",
]
