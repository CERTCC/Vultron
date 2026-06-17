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

"""
Report management behavior tree nodes subpackage.

Re-exports all public node classes from domain-specific submodules so that
existing import paths (``from vultron.core.behaviors.report.nodes import ...``)
continue to work without modification.

Submodules:
- ``conditions``: Validation and prioritization condition nodes
- ``rm_transitions``: Report-management transition action nodes
- ``case_creation``: Case creation and Create(Case) activity nodes
- ``participant``: Case participant RM transition action nodes
- ``emit``: Outbound report activity emission nodes
- ``storage``: Idempotent storage nodes for inbound report objects
"""

from vultron.core.behaviors.helpers import UpdateActorOutbox  # noqa: F401
from vultron.core.behaviors.report.nodes.case_creation import (
    CreateCaseActivity,
    CreateCaseNode,
)
from vultron.core.behaviors.report.nodes.conditions import (
    CheckParticipantExists,
    CheckReportNotClosed,
    CheckRMStateReceivedOrInvalid,
    CheckRMStateValid,
    EnsureEmbargoExists,
    EvaluateCasePriority,
    EvaluateReportCredibility,
    EvaluateReportValidity,
)
from vultron.core.behaviors.report.nodes.emit import (
    EmitCloseReportActivity,
    EmitInvalidateReportActivity,
)
from vultron.core.behaviors.report.nodes.participant import (
    TransitionParticipantRMtoAccepted,
    TransitionParticipantRMtoDeferred,
)
from vultron.core.behaviors.report.nodes.rm_transitions import (
    TransitionCaseParticipantRMtoClosed,
    TransitionCaseParticipantRMtoInvalid,
    TransitionRMtoClosed,
    TransitionRMtoInvalid,
    TransitionRMtoValid,
)
from vultron.core.behaviors.report.nodes.storage import (
    StoreActivityNode,
    StoreReportNode,
)

__all__ = [
    # conditions
    "CheckRMStateValid",
    "CheckRMStateReceivedOrInvalid",
    "CheckReportNotClosed",
    "EnsureEmbargoExists",
    "EvaluateReportCredibility",
    "EvaluateReportValidity",
    "EvaluateCasePriority",
    "CheckParticipantExists",
    # rm_transitions
    "TransitionRMtoValid",
    "TransitionRMtoInvalid",
    "TransitionRMtoClosed",
    "TransitionCaseParticipantRMtoClosed",
    "TransitionCaseParticipantRMtoInvalid",
    # case_creation
    "CreateCaseNode",
    "CreateCaseActivity",
    # participant
    "TransitionParticipantRMtoAccepted",
    "TransitionParticipantRMtoDeferred",
    # emit
    "EmitInvalidateReportActivity",
    "EmitCloseReportActivity",
    # storage
    "StoreReportNode",
    "StoreActivityNode",
    # re-exported from helpers (backward compat)
    "UpdateActorOutbox",
]
