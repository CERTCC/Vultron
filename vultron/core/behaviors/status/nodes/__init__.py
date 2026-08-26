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
- ``conditions``: Participant verification, all-participants-closed precondition,
  and close-not-yet-emitted idempotency guard nodes
- ``broadcast``: (removed — case-manager lookup consolidated into
  ``_resolve_case_manager_id`` in ``vultron.core.use_cases._helpers``)
- ``dimension_filter``: Per-dimension partial-accept guard for inbound
  ParticipantStatus (FilterParticipantStatusDimensionsNode, RSH-05)
- ``append``: Load, resolve and append action nodes
  (SkipIfIdempotentNode, LoadParticipantNode,
  CheckStatusNotAlreadyAppendedNode, ResolveAndPersistStatusObjectNode,
  AppendStatusAndSaveParticipantNode)
- ``rm_validation``: All-or-nothing RM guards for the append sequence
  (ValidateRMTransitionNode, CheckParticipantRMNotClosedNode)
- ``lifecycle``: Public disclosure and auto-close emit lifecycle nodes
  (_PublicDisclosureSkipConditionNode, PublicDisclosureBranchNode,
  ThreatTerminationBranchNode, EmitAddCaseStatusToSelfNode, EmitCloseCaseNode)
- ``rm_anomaly``: RM transition anomaly notification (EmitRMGapNoteNode)
- ``case_status``: Idempotency guard, EM/PXA transition validation, and
  append nodes for the AddCaseStatusToCase workflow
"""

from vultron.core.behaviors.status.nodes.case_status import (
    CASE_STATUS_ALREADY_PRESENT,
    AppendCaseStatusToCaseNode,
    CheckCaseStatusIdempotencyNode,
    ValidateCaseStatusTransitionNode,
)
from vultron.core.behaviors.status.nodes.cs_dimension_filter import (
    BB_CASE_STATUS_DIM_FILTER,
    FilterCsEmDimensionNode,
    FilterCsPxaDimensionNode,
    FinalizeCsFilterNode,
)
from vultron.core.behaviors.status.nodes.conditions import (
    AllParticipantsRMClosedConditionNode,
    CloseNotYetEmittedConditionNode,
    VerifySenderIsParticipantNode,
)
from vultron.core.behaviors.status.nodes.dimension_filter import (
    BB_DIMENSION_FILTER,
    FilterParticipantStatusDimensionsNode,
)
from vultron.core.behaviors.status.nodes.append import (
    AppendStatusAndSaveParticipantNode,
    CheckStatusNotAlreadyAppendedNode,
    LoadParticipantNode,
    ResolveAndPersistStatusObjectNode,
    SkipIfIdempotentNode,
)
from vultron.core.behaviors.status.nodes.rm_validation import (
    CheckParticipantRMNotClosedNode,
    ValidateRMTransitionNode,
)
from vultron.core.behaviors.status.nodes.lifecycle import (
    EmitAddCaseStatusToSelfNode,
    EmitCloseCaseNode,
    PublicDisclosureBranchNode,
    ThreatTerminationBranchNode,
    _PublicDisclosureSkipConditionNode,
)
from vultron.core.behaviors.status.nodes.rm_anomaly import (
    EmitRMGapNoteNode,
)

__all__ = [
    # conditions
    "AllParticipantsRMClosedConditionNode",
    "CloseNotYetEmittedConditionNode",
    "VerifySenderIsParticipantNode",
    # dimension_filter
    "BB_DIMENSION_FILTER",
    "FilterParticipantStatusDimensionsNode",
    # append
    "LoadParticipantNode",
    "CheckStatusNotAlreadyAppendedNode",
    "ResolveAndPersistStatusObjectNode",
    "AppendStatusAndSaveParticipantNode",
    "SkipIfIdempotentNode",
    # rm_validation
    "CheckParticipantRMNotClosedNode",
    "ValidateRMTransitionNode",
    # lifecycle
    "_PublicDisclosureSkipConditionNode",
    "PublicDisclosureBranchNode",
    "ThreatTerminationBranchNode",
    "EmitAddCaseStatusToSelfNode",
    "EmitCloseCaseNode",
    "EmitRMGapNoteNode",
    # case_status
    "BB_CASE_STATUS_DIM_FILTER",
    "CASE_STATUS_ALREADY_PRESENT",
    "CheckCaseStatusIdempotencyNode",
    "FilterCsEmDimensionNode",
    "FilterCsPxaDimensionNode",
    "FinalizeCsFilterNode",
    "ValidateCaseStatusTransitionNode",
    "AppendCaseStatusToCaseNode",
]
