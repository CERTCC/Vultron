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

"""Backward-compatibility re-export shim for core domain model types.

All types have been moved to individual modules under ``vultron/core/models/``.
Import directly from those modules for new code:

- ``vultron.core.models.activity`` — VultronActivity, VultronOffer,
  VultronAccept, VultronCreateCaseActivity
- ``vultron.core.models.case`` — VultronCase
- ``vultron.core.models.case_actor`` — VultronCaseActor, VultronOutbox
- ``vultron.core.models.case_event`` — VultronCaseEvent
- ``vultron.core.models.case_status`` — VultronCaseStatus
- ``vultron.core.models.embargo_event`` — VultronEmbargoEvent
- ``vultron.core.models.note`` — VultronNote
- ``vultron.core.models.participant`` — VultronParticipant
- ``vultron.core.models.participant_status`` — VultronParticipantStatus
- ``vultron.core.models.report`` — VultronReport
"""

from vultron.core.models.activity import (
    VultronAccept,
    VultronActivity,
    VultronCreateCaseActivity,
    VultronOffer,
)
from vultron.core.models.case import VultronCase
from vultron.core.models.case_actor import VultronCaseActor, VultronOutbox
from vultron.core.models.case_event import VultronCaseEvent
from vultron.core.models.case_status import VultronCaseStatus
from vultron.core.models.embargo_event import VultronEmbargoEvent
from vultron.core.models.note import VultronNote
from vultron.core.models.participant import VultronParticipant
from vultron.core.models.participant_status import VultronParticipantStatus
from vultron.core.models.report import VultronReport

__all__ = [
    "VultronAccept",
    "VultronActivity",
    "VultronCase",
    "VultronCaseActor",
    "VultronCaseEvent",
    "VultronCaseStatus",
    "VultronCreateCaseActivity",
    "VultronEmbargoEvent",
    "VultronNote",
    "VultronOffer",
    "VultronOutbox",
    "VultronParticipant",
    "VultronParticipantStatus",
    "VultronReport",
]
