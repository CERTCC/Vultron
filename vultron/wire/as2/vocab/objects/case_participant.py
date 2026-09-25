#!/usr/bin/env python
"""
Wire-layer alias for CaseParticipant.

Per ADR-0099 detail 3: the core class is the canonical form.
The as_-prefixed names are retained for backward compatibility.

``as_CaseParticipant`` was held back with the two status classes by #3487, which
scoped it out because the status pair "drags the as_CaseParticipant cascade with
them".  The cascade turned out to be the cheap part: the two classes carried
identical field sets apart from ``invite_rsvp_deadline`` (core-only, and excluded
from the wire), and core already implemented every method the wire class had —
role serialization, name derivation, status seeding, ``has_role``, ``roles`` —
plus several the wire class did not.  Nothing needed relocating from this class.

The role subclasses continue to be re-exported here so that existing
``from vultron.wire... import VendorParticipant`` imports keep working.
"""

#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
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

from typing import TypeAlias

from vultron.core.models.case_participant import (
    CaseActorParticipant,
    CaseParticipant,
    CoordinatorParticipant,
    DeployerParticipant,
    FinderParticipant,
    FinderReporterParticipant,
    ObserverParticipant,
    ReporterParticipant,
    VendorParticipant,
)
from vultron.core.models.participant_status import ParticipantStatus
from vultron.wire.as2.vocab.base.links import ActivityStreamRef
from vultron.wire.as2.vocab.base.registry import WIRE_TYPE_MAP

__all__ = [
    "CaseActorParticipant",
    "as_CaseParticipant",
    "as_CaseParticipantRef",
    "as_ParticipantStatus",
    "CoordinatorParticipant",
    "DeployerParticipant",
    "FinderParticipant",
    "FinderReporterParticipant",
    "ObserverParticipant",
    "ReporterParticipant",
    "VendorParticipant",
]

as_CaseParticipant = CaseParticipant

# Re-exported from this module historically; kept so existing imports resolve.
as_ParticipantStatus = ParticipantStatus

WIRE_TYPE_MAP["CaseParticipant"] = CaseParticipant

as_CaseParticipantRef: TypeAlias = ActivityStreamRef[CaseParticipant]
