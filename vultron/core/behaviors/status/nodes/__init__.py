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
- ``participant_status_acceptance``: Whole accept-or-reject guard for an
  inbound ParticipantStatus (CheckParticipantStatusAcceptableNode, RSH-09)
- ``case_status_acceptance``: Whole accept-or-reject guard for an inbound
  CaseStatus (CheckCaseStatusAcceptableNode, RSH-09-005)
- ``append``: Load, resolve and append action nodes
  (SkipIfIdempotentNode, LoadParticipantNode,
  CheckStatusNotAlreadyAppendedNode, ResolveAndPersistStatusObjectNode,
  AppendStatusAndSaveParticipantNode)
- ``rm_validation``: RM transition guard for the append sequence
  (ValidateRMTransitionNode)
- ``lifecycle``: Auto-close emit node and the re-exported P/X/A teardown
  branch (ThreatTerminationBranchNode, EmitCloseCaseNode)
- ``rm_anomaly``: RM transition anomaly notification (EmitRMGapNoteNode)
- ``case_status``: Idempotency guard for the AddCaseStatusToCase
  workflow.  EmitCaseStatusUpdateNode (direct ledger
  writes after EM/PXA mutations, RSH-04-002/RSH-04-003) is shared with the
  embargo trees, so it lives in ``vultron.core.behaviors.case_status_snapshot``
  (BTND-04-005)
- ``cs_invariant_diagnostic``: Post-cascade PXA↔EM invariant check
  (PxaEmInvariantDiagnosticNode; CSB-18-002..004, CONCERN-3008)
- ``cs_invariant_guards``: CS ordering invariant precondition guards
  (CheckCsEphemeralStateNode, CheckCsHistoryPrefixNode; CSB-17-012,
  CSB-17-005, ISSUE-2524)
"""

from vultron.core.behaviors.status.nodes.append import (
    AppendStatusAndSaveParticipantNode,
    CheckStatusNotAlreadyAppendedNode,
    LoadParticipantNode,
    ResolveAndPersistStatusObjectNode,
    SkipIfIdempotentNode,
)
from vultron.core.behaviors.status.nodes.case_status import (
    CASE_STATUS_ALREADY_PRESENT,
    CheckCaseStatusIdempotencyNode,
)
from vultron.core.behaviors.status.nodes.case_status_acceptance import (
    CheckCaseStatusAcceptableNode,
)
from vultron.core.behaviors.status.nodes.conditions import (
    AllParticipantsRMClosedConditionNode,
    CloseNotYetEmittedConditionNode,
)
from vultron.core.behaviors.status.nodes.cs_invariant_diagnostic import (
    PxaEmInvariantDiagnosticNode,
)
from vultron.core.behaviors.status.nodes.cs_invariant_guards import (
    CheckCsEphemeralStateNode,
    CheckCsHistoryPrefixNode,
)
from vultron.core.behaviors.status.nodes.lifecycle import (
    EmitCloseCaseNode,
    ThreatTerminationBranchNode,
)
from vultron.core.behaviors.status.nodes.participant_status_acceptance import (
    CheckParticipantStatusAcceptableNode,
)
from vultron.core.behaviors.status.nodes.rm_anomaly import (
    EmitRMGapNoteNode,
    rm_gap_note,
)
from vultron.core.behaviors.status.nodes.rm_validation import (
    ValidateRMTransitionNode,
)

__all__ = [
    # conditions
    "AllParticipantsRMClosedConditionNode",
    "CloseNotYetEmittedConditionNode",
    # participant_status_acceptance
    "CheckParticipantStatusAcceptableNode",
    # append
    "LoadParticipantNode",
    "CheckStatusNotAlreadyAppendedNode",
    "ResolveAndPersistStatusObjectNode",
    "AppendStatusAndSaveParticipantNode",
    "SkipIfIdempotentNode",
    # rm_validation
    "ValidateRMTransitionNode",
    # lifecycle
    "ThreatTerminationBranchNode",
    "EmitCloseCaseNode",
    "EmitRMGapNoteNode",
    "rm_gap_note",
    # cs_invariant_diagnostic
    "PxaEmInvariantDiagnosticNode",
    # case_status
    "CASE_STATUS_ALREADY_PRESENT",
    "CheckCaseStatusIdempotencyNode",
    # case_status_acceptance
    "CheckCaseStatusAcceptableNode",
    # cs_invariant_guards
    "CheckCsEphemeralStateNode",
    "CheckCsHistoryPrefixNode",
]
