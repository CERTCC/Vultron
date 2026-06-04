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
- ``vultron.core.models.case_participant`` — CaseParticipant (and role
  subclasses), VultronParticipant (alias)
- ``vultron.core.models.case_status`` — CaseStatus
- ``vultron.core.models.embargo_event`` — EmbargoEvent (VultronEmbargoEvent is an alias)
- ``vultron.core.models.embargo_policy`` — EmbargoPolicy
- ``vultron.core.models.note`` — VultronNote
- ``vultron.core.models.participant`` — re-export shim (use case_participant)
- ``vultron.core.models.participant_status`` — ParticipantStatus
- ``vultron.core.models.report`` — VulnerabilityReport (VultronReport is an alias)
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
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.embargo_event import EmbargoEvent, VultronEmbargoEvent
from vultron.core.models.embargo_policy import EmbargoPolicy
from vultron.core.models.note import VultronNote
from vultron.core.models.participant import VultronParticipant
from vultron.core.models.case_participant import (
    CaseParticipant,
    CaseActorParticipant,
    CoordinatorParticipant,
    DeployerParticipant,
    FinderParticipant,
    FinderReporterParticipant,
    OtherParticipant,
    ReporterParticipant,
    VendorParticipant,
)
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.report import VulnerabilityReport, VultronReport

__all__ = [
    "VultronAccept",
    "VultronActivity",
    "VultronCase",
    "VultronCaseActor",
    "VultronCaseEvent",
    "CaseActorParticipant",
    "CaseParticipant",
    "CaseStatus",
    "CoordinatorParticipant",
    "DeployerParticipant",
    "EmbargoEvent",
    "EmbargoPolicy",
    "FinderParticipant",
    "FinderReporterParticipant",
    "OtherParticipant",
    "ReporterParticipant",
    "VendorParticipant",
    "VultronCreateCaseActivity",
    "VultronEmbargoEvent",
    "VultronNote",
    "VultronOffer",
    "VultronOutbox",
    "VultronParticipant",
    "ParticipantStatus",
    "VulnerabilityReport",
    "VultronReport",
]
