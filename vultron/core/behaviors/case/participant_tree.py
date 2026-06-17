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
Case participant composite subtrees.

Provides tree-composition classes (``py_trees.composites.Sequence`` /
``Selector`` subclasses) that assemble groups of participant-management
leaf nodes into named subtrees.  These composites belong here at the
process-area root rather than in the ``nodes/`` subpackage, which is
reserved for leaf ``Behaviour`` subclasses (BTND-07-003).

Subtrees defined here:

- ``SeedParticipantAsSignatoryIfEmbargoActiveNode`` — conditionally seeds a
  new participant as SIGNATORY when an active embargo exists.
- ``CreateCaseOwnerParticipant`` — creates and attaches the case-owner
  participant with optional RM advancement.
- ``CreateCaseParticipantNode`` — creates and attaches a non-owner case
  participant with embargo consent seeding and outbox notification.

These subtrees are consumed by ``create_tree.py``,
``receive_report_case_tree.py``, and related tree factories in this package.

Per specs/case-management.yaml CM-02-008, CM-14, and
specs/behavior-tree-node-design.yaml BTND-07-003.
"""

import py_trees

from vultron.core.behaviors.case.nodes.participant.owner import (
    AdvanceOwnerRmToAcceptedNode,
    AttachOwnerParticipantToCaseNode,
    CreateOwnerParticipantNode,
    PersistOwnerCaseNode,
    RecordOwnerJoinedEventNode,
    ResolveOwnerInitialStatusNode,
    ShouldAdvanceOwnerToAcceptedNode,
)
from vultron.core.behaviors.case.nodes.participant.participant_add import (
    AttachParticipantToCaseNode,
    CaseHasActiveEmbargoNode,
    CaseHasNoActiveEmbargoNode,
    CreateParticipantNode,
    QueueAddParticipantNotificationNode,
    RecordParticipantAddedEventNode,
    ResolveParticipantAcceptedStatusNode,
    SeedParticipantAsSignatoryNode,
)
from vultron.core.models.actor_config import ActorConfig
from vultron.core.models.vultron_types import VultronCase
from vultron.core.states.rm import RM
from vultron.core.states.roles import CVDRole


class SeedParticipantAsSignatoryIfEmbargoActiveNode(
    py_trees.composites.Selector
):
    """Conditional subtree for CM-14-005 signatory seeding behavior."""

    def __init__(self, participant_actor_id: str, name: str | None = None):
        super().__init__(
            name=name or self.__class__.__name__,
            memory=False,
            children=[
                py_trees.composites.Sequence(
                    name="SeedWhenActiveEmbargo",
                    memory=False,
                    children=[
                        CaseHasActiveEmbargoNode(),
                        SeedParticipantAsSignatoryNode(
                            participant_actor_id=participant_actor_id
                        ),
                    ],
                ),
                CaseHasNoActiveEmbargoNode(),
            ],
        )


class CreateCaseOwnerParticipant(py_trees.composites.Sequence):
    """
    Composed subtree that creates and attaches the case-owner participant.

    Per specs/case-management.yaml CM-02-008, BTND-05-002, and BTND-07-001.
    """

    def __init__(
        self,
        actor_config: ActorConfig | None = None,
        report_id: str | None = None,
        case_obj: VultronCase | None = None,
        advance_to_accepted: bool = False,
        initial_rm_state: RM = RM.VALID,
        name: str | None = None,
    ):
        super().__init__(
            name=name or self.__class__.__name__,
            memory=False,
            children=[
                ResolveOwnerInitialStatusNode(
                    report_id=report_id,
                    case_obj=case_obj,
                    initial_rm_state=initial_rm_state,
                ),
                CreateOwnerParticipantNode(actor_config=actor_config),
                AttachOwnerParticipantToCaseNode(),
                PersistOwnerCaseNode(),
                RecordOwnerJoinedEventNode(),
                py_trees.composites.Selector(
                    name="AdvanceOwnerRmIfConfigured",
                    memory=False,
                    children=[
                        py_trees.composites.Sequence(
                            name="AdvanceOwnerRmBranch",
                            memory=False,
                            children=[
                                ShouldAdvanceOwnerToAcceptedNode(
                                    advance_to_accepted=advance_to_accepted
                                ),
                                AdvanceOwnerRmToAcceptedNode(),
                            ],
                        ),
                        py_trees.behaviours.Success(name="SkipAdvanceOwnerRm"),
                    ],
                ),
            ],
        )


class CreateCaseParticipantNode(py_trees.composites.Sequence):
    """
    Composed subtree that creates and attaches a CaseParticipant.

    Decomposes participant creation into named leaf nodes so each step is
    explicit and testable (BTND-07-001).
    """

    def __init__(
        self,
        actor_id: str,
        roles: list[CVDRole],
        report_id: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(
            name=name or self.__class__.__name__,
            memory=False,
            children=[
                ResolveParticipantAcceptedStatusNode(
                    participant_actor_id=actor_id,
                    roles=roles,
                    report_id=report_id,
                ),
                CreateParticipantNode(
                    participant_actor_id=actor_id,
                    roles=roles,
                ),
                AttachParticipantToCaseNode(participant_actor_id=actor_id),
                RecordParticipantAddedEventNode(),
                SeedParticipantAsSignatoryIfEmbargoActiveNode(
                    participant_actor_id=actor_id
                ),
                QueueAddParticipantNotificationNode(
                    participant_actor_id=actor_id
                ),
            ],
        )
