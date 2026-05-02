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
Custom Activity Streams Activities for VulnerabilityCase objects.
Each activity should have a VulnerabilityCase object as either its target or object.
"""

from pydantic import Field, model_validator

from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Add,
    as_Announce,
    as_Create,
    as_Ignore,
    as_Invite,
    as_Join,
    as_Leave,
    as_Offer,
    as_Reject,
    as_Update,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor, as_ActorRef
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.case_status import CaseStatus
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    VulnerabilityCase,
    VulnerabilityCaseRef,
    VulnerabilityCaseStub,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)

########################################################################################
# Activities in which the VulnerabilityCase is a target
########################################################################################


class _AddReportToCaseActivity(as_Add):
    """Add a VulnerabilityReport to a VulnerabilityCase
    object_: VulnerabilityReport
    target: VulnerabilityCase
    """

    object_: VulnerabilityReport = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
    target: VulnerabilityCaseRef = None


# add CaseParticipant to VulnerabilityCase
# see _AddParticipantToCaseActivity in case_participant.py


# add CaseStatus to VulnerabilityCase
class _AddStatusToCaseActivity(as_Add):
    """Add a CaseStatus to a VulnerabilityCase.
    This should only be performed by the case owner.
    Other case participants can add a case status to their participant record, which the case
    owner should then add to the case if appropriate.
    object_: CaseStatus
    target: VulnerabilityCase
    """

    object_: CaseStatus = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
    target: VulnerabilityCaseRef = None


########################################################################################
# Activities in which the VulnerabilityCase is an object #
########################################################################################


# create a VulnerabilityCase
class _CreateCaseActivity(as_Create):
    """Create a VulnerabilityCase.
    object_: VulnerabilityCase
    """

    object_: VulnerabilityCase = Field(
        ..., validation_alias="object", serialization_alias="object"
    )


class _CreateCaseStatusActivity(as_Create):
    """Create a CaseStatus.
    object_: CaseStatus
    """

    object_: CaseStatus = Field(
        ..., validation_alias="object", serialization_alias="object"
    )


# Add a Note to a VulnerabilityCase
class _AddNoteToCaseActivity(as_Add):
    """Add a Note to a VulnerabilityCase.
    object_: Note
    target: VulnerabilityCase
    """

    object_: as_Note = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
    target: VulnerabilityCaseRef = None


# update a VulnerabilityCase
class _UpdateCaseActivity(as_Update):
    """Update a VulnerabilityCase.
    object_: VulnerabilityCase
    """

    object_: VulnerabilityCase = Field(
        ..., validation_alias="object", serialization_alias="object"
    )


#####
# Custom Activity Streams Activities specific to the Vultron Protocol
#####


# join a case
class _RmEngageCaseActivity(as_Join):
    """The actor is has joined (i.e., is actively working on) a case.
    This represents the Vultron Message Type RA, and indicates that the actor is now in the RM.ACCEPTED state.
    object_: VulnerabilityCase
    """

    object_: VulnerabilityCase = Field(
        ..., validation_alias="object", serialization_alias="object"
    )


class _RmDeferCaseActivity(as_Ignore):
    """The actor is deferring a case.
    This implies that the actor is no longer actively working on the case.
    Deferring a case does not imply that the actor is abandoning the case entirely,
    it just means that the actor is no longer actively working on it.
    This represents the Vultron Message Type RD, and indicates that the actor is now in the RM.DEFERRED state.
    Contrast with _RmCloseCaseActivity, which indicates that the actor is abandoning the case entirely.
    object_: VulnerabilityCase
    """

    object_: VulnerabilityCase = Field(
        ..., validation_alias="object", serialization_alias="object"
    )


class _RmCloseCaseActivity(as_Leave):
    """The actor is ending their participation in the case and closing their local copy of the case.
    This corresponds to the Vultron RC message type.
    Case closure is considered a permanent Leave from the case.
    If the case owner (attributedTo) is the actor, then the case is closed for all participants.
    If the actor is not the case owner, then the actor should be removed from the case participants.
    object_: VulnerabilityCase
    """

    object_: VulnerabilityCase = Field(
        ..., validation_alias="object", serialization_alias="object"
    )


class _OfferCaseOwnershipTransferActivity(as_Offer):
    """The actor is offering to transfer ownership of the case to another actor.

    The case MUST be provided as an inline ``VulnerabilityCase`` object so that
    the recipient can identify the object type unambiguously during semantic
    pattern matching.  Passing only a string URI makes the activity
    indistinguishable from a ``SUBMIT_REPORT`` Offer and causes incorrect
    dispatch.

    object_: VulnerabilityCase (inline — not a bare string ID)
    target: as_Actor
    """

    object_: VulnerabilityCase = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
    target: as_ActorRef = None


class _AcceptCaseOwnershipTransferActivity(as_Accept):
    """The actor is accepting an offer to transfer ownership of the case.

    - object_: the _OfferCaseOwnershipTransferActivity being accepted (inline
      typed object required — bare string IDs are rejected at construction time)
    """

    object_: _OfferCaseOwnershipTransferActivity = Field(
        ..., validation_alias="object", serialization_alias="object"
    )


class _RejectCaseOwnershipTransferActivity(as_Reject):
    """The actor is rejecting an offer to transfer ownership of the case.

    - object_: the _OfferCaseOwnershipTransferActivity being rejected (inline
      typed object required — bare string IDs are rejected at construction time)
    """

    object_: _OfferCaseOwnershipTransferActivity = Field(
        ..., validation_alias="object", serialization_alias="object"
    )


class _RmInviteToCaseActivity(as_Invite):
    """The actor is inviting another actor to a case.
    This corresponds to the Vultron Message Type RS when a case already exists.
    See also _RmSubmitReportActivity for the scenario when a case does not exist yet.
    object_: the Actor being invited
    target: VulnerabilityCase
    """

    object_: as_Actor = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
    target: VulnerabilityCaseStub | str | None = None


class _RmAcceptInviteToCaseActivity(as_Accept):
    """The actor is accepting an invitation to a case.
    This corresponds to the Vultron Message Type RV when the case already exists.
    See also _RmValidateReportActivity for the scenario when the case does not exist yet.

    object_: the _RmInviteToCaseActivity being accepted (inline typed object
        required — bare string IDs are rejected at construction time)
    """

    object_: _RmInviteToCaseActivity = Field(
        ..., validation_alias="object", serialization_alias="object"
    )

    @model_validator(mode="after")
    def set_in_reply_to_from_invite(self):
        if self.in_reply_to is None:
            self.in_reply_to = self.object_.id_
        return self


class _RmRejectInviteToCaseActivity(as_Reject):
    """The actor is rejecting an invitation to a case.
    This corresponds to the Vultron Message Type RI when the case already exists.
    See also _RmInvalidateReportActivity for the scenario when the case does not exist yet.

    `object_`: the `_RmInviteToCaseActivity` being rejected (inline typed
        object required — bare string IDs are rejected at construction time)
    """

    object_: _RmInviteToCaseActivity = Field(
        ..., validation_alias="object", serialization_alias="object"
    )

    @model_validator(mode="after")
    def set_in_reply_to_from_invite(self):
        if self.in_reply_to is None:
            self.in_reply_to = self.object_.id_
        return self


class _AnnounceVulnerabilityCaseActivity(as_Announce):
    """The case owner announces full case details to a newly accepted invitee.

    Sent by the case owner after an ``Accept(Invite)`` is received and the
    invitee's embargo consent has been verified (MV-10-003 through MV-10-006).
    The full :class:`VulnerabilityCase` is sent as the inline object so the
    recipient can seed their local DataLayer.

    ``object_``: :class:`VulnerabilityCase` — the complete case object.
    """

    object_: VulnerabilityCase = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
