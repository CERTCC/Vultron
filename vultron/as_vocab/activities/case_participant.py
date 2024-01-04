#!/usr/bin/env python
#  Copyright (c) 2023-2024 Carnegie Mellon University and Contributors.
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

from dataclasses import dataclass, field
from typing import Optional, Union

from dataclasses_json import LetterCase, config, dataclass_json

from vultron.as_vocab.base.links import as_Link
from vultron.as_vocab.base.objects.activities.transitive import (
    as_Add,
    as_Create,
    as_Remove,
)
from vultron.as_vocab.objects.case_participant import CaseParticipant
from vultron.as_vocab.objects.case_status import ParticipantStatus
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class CreateStatusForParticipant(as_Create):
    """Create a new CaseStatus for a CaseParticipant"""

    as_type: str = field(default="Create", init=False)
    as_object: Optional[Union[ParticipantStatus, as_Link]] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )
    target: Optional[Union[CaseParticipant, as_Link]] = field(default=None)


# add CaseStatus to CaseParticipant
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class AddStatusToParticipant(as_Add):
    """Add a CaseStatus to a CaseParticipant
    as_object: CaseStatus
    target: CaseParticipant
    """

    as_type: str = field(default="Add", init=False)
    as_object: Optional[Union[ParticipantStatus, as_Link]] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )
    target: Optional[Union[CaseParticipant, as_Link]] = field(default=None)


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class AddParticipantToCase(as_Add):
    """Add a CaseParticipant to a VulnerabilityCase
    as_object: CaseParticipant
    target: VulnerabilityCase
    """

    as_type: str = field(default="Add", init=False)
    as_object: Optional[Union[CaseParticipant, as_Link]] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )
    target: Optional[Union[VulnerabilityCase, as_Link]] = field(default=None)


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class RemoveParticipantFromCase(as_Remove):
    """Remove a CaseParticipant from a VulnerabilityCase.
    This should only be performed by the case owner.
    as_object: CaseParticipant
    origin: VulnerabilityCase
    """

    as_type: str = field(default="Remove", init=False)
    as_object: Optional[Union[CaseParticipant, as_Link]] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )
    origin: Optional[Union[VulnerabilityCase, as_Link]] = field(default=None)
