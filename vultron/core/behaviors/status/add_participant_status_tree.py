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
AddParticipantStatus behavior tree composition.

Composes the five-step DEMOMA-07-003 workflow as a Sequence BT:

    AddParticipantStatusBT (Sequence)
    ├─ VerifySenderIsParticipantNode   # Step 1: sender must be known participant
    ├─ AppendParticipantStatusNode     # Step 2: append status to participant record
    ├─ BroadcastStatusToPeersNode      # Step 3: Case Manager broadcasts to peers
    ├─ PublicDisclosureBranchNode      # Step 4: embargo teardown on CS.P + CASE_OWNER
    └─ AutoCloseBranchNode             # Step 5: log auto-close if all RM.CLOSED

Per specs/multi-actor-demo.yaml DEMOMA-07-003.
"""

import logging

import py_trees

from vultron.core.models.events.status import (
    AddParticipantStatusToParticipantReceivedEvent,
)
from vultron.core.behaviors.status.nodes import (
    AppendParticipantStatusNode,
    AutoCloseBranchNode,
    BroadcastStatusToPeersNode,
    PublicDisclosureBranchNode,
    VerifySenderIsParticipantNode,
)

logger = logging.getLogger(__name__)


def add_participant_status_tree(
    request: AddParticipantStatusToParticipantReceivedEvent,
) -> py_trees.behaviour.Behaviour:
    """Create the behavior tree for the AddParticipantStatus workflow.

    Handles receipt of an ``Add(ParticipantStatus, CaseParticipant)``
    activity.  Implements all five steps of DEMOMA-07-003 as BT nodes
    in a Sequence.

    The *case_id* is derived from the inline ``request.status.context``
    field.  If it is not available in the inline object, the
    ``VerifySenderIsParticipantNode`` will perform a DataLayer lookup.

    ``BroadcastStatusToPeersNode`` and ``PublicDisclosureBranchNode`` use
    the ``trigger_activity_factory`` that the caller places on the
    py_trees blackboard via ``BTBridge(trigger_activity=...)``.

    Args:
        request: The parsed inbound domain event.

    Returns:
        Root node of the ``AddParticipantStatusBT`` Sequence.
    """
    status_id = request.status_id or ""
    participant_id = request.participant_id or ""
    actor_id = request.actor_id
    status_obj = request.status

    # Derive case_id from the inline status object when available.
    # VerifySenderIsParticipantNode falls back to a DataLayer lookup when None.
    case_id: str | None = None
    if status_obj is not None:
        context_field = getattr(status_obj, "context", None)
        if context_field:
            case_id = str(context_field)

    root = py_trees.composites.Sequence(
        name="AddParticipantStatusBT",
        memory=False,
        children=[
            VerifySenderIsParticipantNode(
                status_id=status_id,
                sender_actor_id=actor_id,
                case_id=case_id,
            ),
            AppendParticipantStatusNode(
                status_id=status_id,
                participant_id=participant_id,
                status_obj_fallback=status_obj,
            ),
            BroadcastStatusToPeersNode(
                status_id=status_id,
                participant_id=participant_id,
                sender_actor_id=actor_id,
                case_id=case_id,
            ),
            PublicDisclosureBranchNode(
                status_obj=status_obj,
                sender_actor_id=actor_id,
                case_id=case_id,
            ),
            AutoCloseBranchNode(
                case_id=case_id,
            ),
        ],
    )
    logger.debug(
        "Created AddParticipantStatusBT for status=%s participant=%s"
        " actor=%s case=%s",
        status_id,
        participant_id,
        actor_id,
        case_id,
    )
    return root
