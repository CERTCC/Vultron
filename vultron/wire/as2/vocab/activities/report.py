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
This module contains extensions to the ActivityStreams Vocabulary for Vultron activities related to
VulnerabilityReports.
"""

from pydantic import Field

from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Create,
    as_Offer,
    as_Read,
    as_Reject,
    as_TentativeReject,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)


class RmCreateReportActivity(as_Create):
    """The actor is creating a report."""

    object_: VulnerabilityReport = Field(
        ..., validation_alias="object", serialization_alias="object"
    )


class RmSubmitReportActivity(as_Offer):
    """The actor is submitting a report to another actor
    This corresponds to the Vultron RS message type when no case exists.
    See also RmInviteToCaseActivity for the scenario when a case already exists.
    object_: VulnerabilityReport
    """

    object_: VulnerabilityReport = Field(
        ..., validation_alias="object", serialization_alias="object"
    )


class RmReadReportActivity(as_Read):
    """The actor has read a report.
    This corresponds to the Vultron Message Type RK when no case exists.
    object_: VulnerabilityReport
    """

    object_: VulnerabilityReport = Field(
        ..., validation_alias="object", serialization_alias="object"
    )


class RmValidateReportActivity(as_Accept):
    """The actor has validated a report.
    Corresponds to the Vultron Message Type RV when no case exists.
    This should be followed by a Create(VulnerabilityCase) activity.

    object_: the RmSubmitReportActivity offer wrapping the VulnerabilityReport
        (inline typed object required — bare string IDs are rejected at
        construction time)
    """

    object_: RmSubmitReportActivity = Field(
        ..., validation_alias="object", serialization_alias="object"
    )


class RmInvalidateReportActivity(as_TentativeReject):
    """The actor has invalidated a report.
    Corresponds to the Vultron Message Type RI when no case exists.
    See also RmRejectInviteToCaseActivity for the scenario when a case already exists.

    object_: the RmSubmitReportActivity offer wrapping the VulnerabilityReport
        (inline typed object required — bare string IDs are rejected at
        construction time)
    """

    object_: RmSubmitReportActivity = Field(
        ..., validation_alias="object", serialization_alias="object"
    )


class RmCloseReportActivity(as_Reject):
    """The actor is closing the report.
    This corresponds to the Vultron Message Type RC when no case exists.
    It can only be emitted when the report is in the RM.INVALID state, because anything past that will
    have an associated VulnerabilityCase object, and closure of the case falls to the RmCloseCaseActivity activity.

    object_: the RmSubmitReportActivity offer wrapping the VulnerabilityReport
        (inline typed object required — bare string IDs are rejected at
        construction time)
    """

    object_: RmSubmitReportActivity = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
