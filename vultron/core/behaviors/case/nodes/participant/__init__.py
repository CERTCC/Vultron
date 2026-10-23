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

Participant records are built and attached through the policy-free
``_create_and_attach_participant`` helper; each seating flow (case owner,
inert invitee, reporter) supplies its own roles and initial status
(BTND-05-003).
"""

from vultron.core.behaviors.case.nodes.participant.common import (
    _create_and_attach_participant,
    resolve_participant_state_from_dl,
)
from vultron.core.behaviors.case.nodes.participant.status import (
    CreateParticipantStatusNode,
)
from vultron.core.behaviors.case.nodes.participant.trigger_validation import (
    ValidateTriggerTransitionsNode,
)

__all__ = [
    "_create_and_attach_participant",
    "resolve_participant_state_from_dl",
    "CreateParticipantStatusNode",
    "ValidateTriggerTransitionsNode",
]
