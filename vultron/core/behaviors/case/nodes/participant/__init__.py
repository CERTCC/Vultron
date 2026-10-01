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

Composite subtrees (``Sequence``/``Selector`` subclasses) for participant
workflows are defined in ``participant_tree.py`` at the process-area root
(BTND-07-003).  They are not re-exported here: ``participant_tree.py``
imports leaf nodes from this package, so a re-export would close an import
cycle (CS-05-003).
"""

from vultron.core.behaviors.case.nodes.participant.common import (
    _create_and_attach_participant,
    _queue_participant_add_notification,
    resolve_participant_state_from_dl,
)
from vultron.core.behaviors.case.nodes.participant.owner import (
    AttachOwnerParticipantToCaseNode,
    CreateOwnerInitialStatusNode,
    CreateOwnerParticipantNode,
    PersistOwnerCaseNode,
    RecordOwnerJoinedEventNode,
    _effective_case_roles,
)
from vultron.core.behaviors.case.nodes.participant.participant_add import (
    AttachParticipantToCaseNode,
    CaseHasActiveEmbargoNode,
    CaseHasNoActiveEmbargoNode,
    CreateParticipantInitialStatusNode,
    CreateParticipantNode,
    QueueAddParticipantNotificationNode,
    RecordParticipantAddedEventNode,
    SeedParticipantAsSignatoryNode,
)
from vultron.core.behaviors.case.nodes.participant.status import (
    CreateParticipantStatusNode,
)
from vultron.core.behaviors.case.nodes.participant.trigger_validation import (
    ValidateTriggerTransitionsNode,
)

__all__ = [
    "_create_and_attach_participant",
    "_effective_case_roles",
    "_queue_participant_add_notification",
    "resolve_participant_state_from_dl",
    "CreateOwnerInitialStatusNode",
    "CreateOwnerParticipantNode",
    "AttachOwnerParticipantToCaseNode",
    "PersistOwnerCaseNode",
    "RecordOwnerJoinedEventNode",
    "CreateParticipantInitialStatusNode",
    "CreateParticipantNode",
    "AttachParticipantToCaseNode",
    "RecordParticipantAddedEventNode",
    "CaseHasActiveEmbargoNode",
    "CaseHasNoActiveEmbargoNode",
    "SeedParticipantAsSignatoryNode",
    "QueueAddParticipantNotificationNode",
    "CreateParticipantStatusNode",
    "ValidateTriggerTransitionsNode",
]
