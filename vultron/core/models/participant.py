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

"""Backward-compatibility re-export shim for the core participant type.

The canonical implementation has moved to
:mod:`vultron.core.models.case_participant`.  Import from there for new code.
"""

from vultron.core.models.case_participant import (  # noqa: F401
    CaseParticipant,
    CaseActorParticipant,
    CoordinatorParticipant,
    DeployerParticipant,
    FinderParticipant,
    FinderReporterParticipant,
    OtherParticipant,
    ReporterParticipant,
    VendorParticipant,
    VultronParticipant,
)

__all__ = [
    "CaseActorParticipant",
    "CaseParticipant",
    "CoordinatorParticipant",
    "DeployerParticipant",
    "FinderParticipant",
    "FinderReporterParticipant",
    "OtherParticipant",
    "ReporterParticipant",
    "VendorParticipant",
    "VultronParticipant",
]
