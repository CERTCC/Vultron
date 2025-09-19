#!/usr/bin/env python
#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""
Provides Vultron ActivityStreams Activities related to CaseParticipants
"""

from typing import Literal

from pydantic import Field

from vultron.as_vocab.base.links import as_Link
from vultron.as_vocab.base.objects.activities.transitive import (
    as_Add,
    as_Create,
    as_Remove,
)
from vultron.as_vocab.objects.case_participant import CaseParticipant
from vultron.as_vocab.objects.case_status import ParticipantStatus
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase


class CreateParticipant(as_Create):
    """Create a new CaseParticipant"""

    as_type: Literal["Create"] = "Create"
    as_object: CaseParticipant | as_Link | str | None = Field(
        None, alias="object"
    )
    target: VulnerabilityCase | as_Link | str | None = None


class CreateStatusForParticipant(as_Create):
    """Create a new CaseStatus for a CaseParticipant"""

    as_type: Literal["Create"] = "Create"
    as_object: ParticipantStatus | as_Link | str | None = Field(
        None, alias="object"
    )
    target: CaseParticipant | as_Link | str | None = None


# add CaseStatus to CaseParticipant
class AddStatusToParticipant(as_Add):
    """Add a CaseStatus to a CaseParticipant
    as_object: CaseStatus
    target: CaseParticipant
    """

    as_type: Literal["Add"] = "Add"
    as_object: ParticipantStatus | as_Link | str | None = Field(
        None, alias="object"
    )
    target: CaseParticipant | as_Link | str | None = None


class AddParticipantToCase(as_Add):
    """Add a CaseParticipant to a VulnerabilityCase
    as_object: CaseParticipant
    target: VulnerabilityCase
    """

    as_type: Literal["Add"] = "Add"
    as_object: CaseParticipant | as_Link | str | None = Field(
        None, alias="object"
    )
    as_target: VulnerabilityCase | as_Link | str | None = None


class RemoveParticipantFromCase(as_Remove):
    """Remove a CaseParticipant from a VulnerabilityCase.
    This should only be performed by the case owner.
    as_object: CaseParticipant
    origin: VulnerabilityCase
    """

    as_type: Literal["Remove"] = "Remove"
    as_object: CaseParticipant | as_Link | str | None = Field(
        None, alias="object"
    )
    origin: VulnerabilityCase | as_Link | str | None = None
