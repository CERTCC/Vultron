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
Case management behavior tree nodes subpackage.

Re-exports all public node classes from domain-specific submodules so that
existing import paths (``from vultron.core.behaviors.case.nodes import ...``)
continue to work without modification.

Submodules:
- ``conditions``: Idempotency guard condition nodes
- ``case_setup``: Case persistence and actor setup action nodes
- ``participant``: Participant creation and attachment action nodes
- ``embargo``: Default embargo initialization action nodes
- ``communication``: Outbound activity emission action nodes
- ``lifecycle``: Case log entry commit action node
"""

from vultron.core.behaviors.case.nodes.case_setup import (
    CreateCaseActorNode,
    PersistCase,
    RecordCaseCreationEvents,
    SetCaseAttributedTo,
)
from vultron.core.behaviors.case.nodes.communication import (
    EmitCreateCaseActivity,
    SendOfferCaseManagerRoleNode,
)
from vultron.core.behaviors.case.nodes.conditions import (
    CheckCaseAlreadyExists,
    CheckCaseExistsForReport,
    ValidateCaseObject,
)
from vultron.core.behaviors.case.nodes.embargo import (
    InitializeDefaultEmbargoNode,
)
from vultron.core.behaviors.case.nodes.lifecycle import CommitCaseLogEntryNode
from vultron.core.behaviors.case.nodes.participant import (
    CreateCaseOwnerParticipant,
    CreateCaseParticipantNode,
    _create_and_attach_participant,
)
from vultron.core.behaviors.helpers import UpdateActorOutbox  # noqa: F401

__all__ = [
    # conditions
    "CheckCaseAlreadyExists",
    "CheckCaseExistsForReport",
    "ValidateCaseObject",
    # case_setup
    "PersistCase",
    "SetCaseAttributedTo",
    "RecordCaseCreationEvents",
    "CreateCaseActorNode",
    # participant
    "CreateCaseOwnerParticipant",
    "CreateCaseParticipantNode",
    "_create_and_attach_participant",
    # embargo
    "InitializeDefaultEmbargoNode",
    # communication
    "EmitCreateCaseActivity",
    "SendOfferCaseManagerRoleNode",
    # lifecycle
    "CommitCaseLogEntryNode",
    # re-exported from helpers (backward compat)
    "UpdateActorOutbox",
]
