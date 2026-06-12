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
Participant management behavior-tree nodes for case workflows.

This package replaces the previous monolithic ``participant.py`` module while
preserving its public import surface.
"""

from vultron.core.behaviors.case.nodes.participant.common import (
    _create_and_attach_participant,
    _get_or_create_accepted_status,
    _queue_participant_add_notification,
    resolve_participant_state_from_dl,
)
from vultron.core.behaviors.case.nodes.participant.owner import (
    AdvanceOwnerRmToAcceptedNode,
    AttachOwnerParticipantToCaseNode,
    CreateCaseOwnerParticipant,
    CreateOwnerParticipantNode,
    PersistOwnerCaseNode,
    RecordOwnerJoinedEventNode,
    _build_owner_initial_status,
    _effective_case_roles,
    _resolve_case_id,
    ResolveOwnerInitialStatusNode,
    ShouldAdvanceOwnerToAcceptedNode,
)
from vultron.core.behaviors.case.nodes.participant.participant_add import (
    AttachParticipantToCaseNode,
    CaseHasActiveEmbargoNode,
    CaseHasNoActiveEmbargoNode,
    CreateCaseParticipantNode,
    CreateParticipantNode,
    EnsureReporterParticipantAtAcceptedNode,
    QueueAddParticipantNotificationNode,
    RecordParticipantAddedEventNode,
    ResolveParticipantAcceptedStatusNode,
    SeedParticipantAsSignatoryIfEmbargoActiveNode,
    SeedParticipantAsSignatoryNode,
)
from vultron.core.behaviors.case.nodes.participant.status import (
    CreateParticipantStatusNode,
)

__all__ = [
    "_create_and_attach_participant",
    "_resolve_case_id",
    "_build_owner_initial_status",
    "_effective_case_roles",
    "_get_or_create_accepted_status",
    "_queue_participant_add_notification",
    "resolve_participant_state_from_dl",
    "ResolveOwnerInitialStatusNode",
    "CreateOwnerParticipantNode",
    "AttachOwnerParticipantToCaseNode",
    "PersistOwnerCaseNode",
    "ShouldAdvanceOwnerToAcceptedNode",
    "AdvanceOwnerRmToAcceptedNode",
    "RecordOwnerJoinedEventNode",
    "CreateCaseOwnerParticipant",
    "ResolveParticipantAcceptedStatusNode",
    "CreateParticipantNode",
    "AttachParticipantToCaseNode",
    "RecordParticipantAddedEventNode",
    "CaseHasActiveEmbargoNode",
    "CaseHasNoActiveEmbargoNode",
    "SeedParticipantAsSignatoryNode",
    "SeedParticipantAsSignatoryIfEmbargoActiveNode",
    "QueueAddParticipantNotificationNode",
    "CreateCaseParticipantNode",
    "CreateParticipantStatusNode",
    "EnsureReporterParticipantAtAcceptedNode",
]
