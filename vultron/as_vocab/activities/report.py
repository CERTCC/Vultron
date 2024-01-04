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
This module contains extensions to the ActivityStreams Vocabulary for Vultron activities related to
VulnerabilityReports.
"""

from dataclasses import dataclass, field
from typing import Optional, Union

from dataclasses_json import LetterCase, config, dataclass_json

from vultron.as_vocab.base.links import as_Link
from vultron.as_vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Create,
    as_Leave,
    as_Offer,
    as_Read,
    as_Reject,
)
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class RmCreateReport(as_Create):
    """The actor is creating a report."""

    as_type: str = "Create"
    as_object: Optional[Union[VulnerabilityReport, as_Link]] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class RmSubmitReport(as_Offer):
    """The actor is submitting a report to another actor
    This corresponds to the Vultron RS message type when no case exists.
    See also RmInviteToCase for the scenario when a case already exists.
    as_object: VulnerabilityReport
    """

    as_type: str = "Offer"
    as_object: Optional[Union[VulnerabilityReport, as_Link]] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class RmReadReport(as_Read):
    """The actor has read a report.
    This corresponds to the Vultron Message Type RK when no case exists.
    as_object: VulnerabilityReport
    """

    as_type: str = "Read"
    as_object: Optional[Union[VulnerabilityReport, as_Link]] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class RmValidateReport(as_Accept):
    """The actor has validated a report.
    Corresponds to the Vultron Message Type RV when no case exists.
    This should be followed by a Create(VulnerabilityCase) activity.
    as_object: VulnerabilityReport
    """

    as_type: str = "Accept"
    as_object: Optional[Union[VulnerabilityReport, as_Link]] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class RmInvalidateReport(as_Reject):
    """The actor has invalidated a report.
    Corresponds to the Vultron Message Type RI when no case exists.
    See also RmRejectInviteToCase for the scenario when a case already exists.
    as_object: VulnerabilityReport
    """

    as_type: str = "Reject"
    as_object: Optional[Union[VulnerabilityReport, as_Link]] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class RmCloseReport(as_Leave):
    """The actor is closing the report.
    This corresponds to the Vultron Message Type RC when no case exists.
    It can only be emitted when the report is in the RM.INVALID state, because anything past that will
    have an associated VulnerabilityCase object, and closure of the case falls to the RmCloseCase activity.
    as_object: VulnerabilityReport
    """

    as_object: Optional[Union[VulnerabilityReport, as_Link]] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )
