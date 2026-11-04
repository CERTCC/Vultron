#!/usr/bin/env python
# pyright: reportGeneralTypeIssues=false
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
"""Case activities that create, update, announce or add content to a case."""

from typing import ClassVar

from pydantic import Field

from vultron.primitives import NonEmptyString
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Add,
    as_Announce,
    as_Create,
    as_Update,
)
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.case_status import as_CaseStatus
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
    as_VulnerabilityCaseRef,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

########################################################################################
# Activities in which the VulnerabilityCase is a target
########################################################################################


class _AddReportToCaseActivity(as_Add):
    """Add a VulnerabilityReport to a VulnerabilityCase
    object_: as_VulnerabilityReport
    target: as_VulnerabilityCase
    """

    object_: as_VulnerabilityReport = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
    target: as_VulnerabilityCaseRef = None
    # The report's Offer provenance, carried on the CASE_MANAGER's
    # ``add_report_to_case`` entry for the case's participants, who were never
    # sent the Offer (CP-01-007, CM-11-020).  The same pair, and the same
    # wire keys, as ``as_CaseProposal.offer_id``/``offer_actor_id``.
    offer_id: NonEmptyString | None = Field(
        default=None,
        validation_alias="offerId",
        serialization_alias="offerId",
        description="URI of the Offer(VulnerabilityReport) the report arrived in.",
    )
    offer_actor_id: NonEmptyString | None = Field(
        default=None,
        validation_alias="offerActorId",
        serialization_alias="offerActorId",
        description="URI of the actor that sent the Offer named by offer_id.",
    )


# add CaseParticipant to VulnerabilityCase
# see _AddParticipantToCaseActivity in case_participant.py


# add CaseStatus to VulnerabilityCase
class _AddStatusToCaseActivity(as_Add):
    """Add a CaseStatus to a VulnerabilityCase.
    This should only be performed by the case owner.
    Other case participants can add a case status to their participant record, which the case
    owner should then add to the case if appropriate.
    object_: as_CaseStatus
    target: as_VulnerabilityCase
    """

    object_: as_CaseStatus = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
    target: as_VulnerabilityCaseRef = None


########################################################################################
# Activities in which the VulnerabilityCase is an object #
########################################################################################


# create a VulnerabilityCase
class _CreateCaseActivity(as_Create):
    """Create a VulnerabilityCase.
    object_: as_VulnerabilityCase
    """

    object_: as_VulnerabilityCase = Field(
        ..., validation_alias="object", serialization_alias="object"
    )


# Add a Note to a VulnerabilityCase
class _AddNoteToCaseActivity(as_Add):
    """Add a Note to a VulnerabilityCase.
    object_: Note
    target: as_VulnerabilityCase
    """

    object_: as_Note = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
    target: as_VulnerabilityCaseRef = None


# update a VulnerabilityCase
class _UpdateCaseActivity(as_Update):
    """Update a VulnerabilityCase.

    The CASE_MANAGER's own act naming a new Case Owner, committed as its
    ``update_case_owner`` ledger entry (CM-21-024, CLP-07-013).  The registry
    recognizes it, but no received use case handles it, so an inbox reports
    a received one as "no use case found" (ADR-0140).

    object_: as_VulnerabilityCase
    """

    object_: as_VulnerabilityCase = Field(
        ..., validation_alias="object", serialization_alias="object"
    )


class _AnnounceVulnerabilityCaseActivity(as_Announce):
    """The case owner announces full case details to a newly accepted invitee.

    Sent by the case owner after an ``Accept(Invite)`` is received and the
    invitee's embargo consent has been verified (MV-10-003 through MV-10-006).
    The full :class:`VulnerabilityCase` is sent as the inline object so the
    recipient can seed their local DataLayer.

    ``object_``: :class:`VulnerabilityCase` — the complete case object.

    Declares ``object_`` in :attr:`inline_required_refs` (DL-08-001): the
    copy is the message, not a reference to the case the receiver already
    holds.  Collapsed to an id, the receiver's rebuild of the activity read
    back its own stored case instead of the copy, so a replica holding the
    case could never be updated by one, and the copy's ledger position was
    lost (SYNC-16-005, SYNC-16-006).
    """

    object_: as_VulnerabilityCase = Field(
        ..., validation_alias="object", serialization_alias="object"
    )

    inline_required_refs: ClassVar[frozenset[str]] = frozenset({"object_"})
