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

"""Domain representation of a case participant and role subclasses.

``CaseParticipant`` is the canonical core type.

Several convenience subclasses are provided that auto-set ``case_roles`` via
model validators:

- :class:`ReporterParticipant`
- :class:`VendorParticipant`
- :class:`DeployerParticipant`
- :class:`CoordinatorParticipant`
- :class:`ObserverParticipant`
- :class:`CaseActorParticipant`

Grouped by concern (CS-18-005):

- ``participant`` — the :class:`CaseParticipant` model, its status ladder and roles
- ``_consent`` — its per-embargo consent rows (ADR-0122)
- ``roles`` — the role subclasses
"""

from vultron.core.models.case_participant.participant import (
    CaseParticipant,
)
from vultron.core.models.case_participant.roles import (
    CaseActorParticipant,
    CoordinatorParticipant,
    DeployerParticipant,
    ObserverParticipant,
    ReporterParticipant,
    VendorParticipant,
)

__all__ = [
    "CaseActorParticipant",
    "CaseParticipant",
    "CoordinatorParticipant",
    "DeployerParticipant",
    "ObserverParticipant",
    "ReporterParticipant",
    "VendorParticipant",
]
