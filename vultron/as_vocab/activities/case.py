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

from typing import TypeAlias

from pydantic import Field

from vultron.as_vocab.base.links import ActivityStreamRef
from vultron.as_vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Add,
    as_Create,
    as_Ignore,
    as_Invite,
    as_Join,
    as_Leave,
    as_Offer,
    as_Reject,
    as_Update,
)
from vultron.as_vocab.base.objects.actors import as_ActorRef
from vultron.as_vocab.base.objects.object_types import as_NoteRef
from vultron.as_vocab.objects.case_status import CaseStatusRef
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCaseRef
from vultron.as_vocab.objects.vulnerability_report import (
    VulnerabilityReportRef,
)

########################################################################################
# Activities in which the VulnerabilityCase is a target
########################################################################################


class AddReportToCase(as_Add):
    """Add a VulnerabilityReport to a VulnerabilityCase
    as_object: VulnerabilityReport
    target: VulnerabilityCase
    """

    as_object: VulnerabilityReportRef = Field(None, alias="object")
    target: VulnerabilityCaseRef = None


# add CaseParticipant to VulnerabilityCase
# see AddParticipantToCase in case_participant.py


# add CaseStatus to VulnerabilityCase
class AddStatusToCase(as_Add):
    """Add a CaseStatus to a VulnerabilityCase.
    This should only be performed by the case owner.
    Other case participants can add a case status to their participant record, which the case
    owner should then add to the case if appropriate.
    as_object: CaseStatus
    target: VulnerabilityCase
    """

    as_object: CaseStatusRef = Field(None, alias="object")
    target: VulnerabilityCaseRef = None


########################################################################################
# Activities in which the VulnerabilityCase is an object #
########################################################################################


# create a VulnerabilityCase
class CreateCase(as_Create):
    """Create a VulnerabilityCase.
    as_object: VulnerabilityCase
    """

    as_object: VulnerabilityCaseRef = Field(None, alias="object")


class CreateCaseStatus(as_Create):
    """Create a CaseStatus.
    as_object: CaseStatus
    """

    as_object: CaseStatusRef = Field(None, alias="object")


# Add a Note to a VulnerabilityCase
class AddNoteToCase(as_Add):
    """Add a Note to a VulnerabilityCase.
    as_object: Note
    target: VulnerabilityCase
    """

    as_object: as_NoteRef = Field(None, alias="object")
    target: VulnerabilityCaseRef = None


# update a VulnerabilityCase
class UpdateCase(as_Update):
    """Update a VulnerabilityCase.
    as_object: VulnerabilityCase
    """

    as_object: VulnerabilityCaseRef = Field(None, alias="object")


#####
# Custom Activity Streams Activities specific to the Vultron Protocol
#####


# join a case
class RmEngageCase(as_Join):
    """The actor is has joined (i.e., is actively working on) a case.
    This represents the Vultron Message Type RA, and indicates that the actor is now in the RM.ACCEPTED state.
    as_object: VulnerabilityCase
    """

    as_object: VulnerabilityCaseRef = Field(None, alias="object")


class RmDeferCase(as_Ignore):
    """The actor is deferring a case.
    This implies that the actor is no longer actively working on the case.
    Deferring a case does not imply that the actor is abandoning the case entirely,
    it just means that the actor is no longer actively working on it.
    This represents the Vultron Message Type RD, and indicates that the actor is now in the RM.DEFERRED state.
    Contrast with RmCloseCase, which indicates that the actor is abandoning the case entirely.
    as_object: VulnerabilityCase
    """

    as_object: VulnerabilityCaseRef = Field(None, alias="object")


class RmCloseCase(as_Leave):
    """The actor is ending their participation in the case and closing their local copy of the case.
    This corresponds to the Vultron RC message type.
    Case closure is considered a permanent Leave from the case.
    If the case owner (attributedTo) is the actor, then the case is closed for all participants.
    If the actor is not the case owner, then the actor should be removed from the case participants.
    as_object: VulnerabilityCase
    """

    as_object: VulnerabilityCaseRef = Field(None, alias="object")


class OfferCaseOwnershipTransfer(as_Offer):
    """The actor is offering to transfer ownership of the case to another actor.
    as_object: VulnerabilityCase
    target: as_Actor
    """

    as_object: VulnerabilityCaseRef = Field(None, alias="object")
    target: as_ActorRef = None


class AcceptCaseOwnershipTransfer(as_Accept):
    """The actor is accepting an offer to transfer ownership of the case.

    - as_object: VulnerabilityCase
    - in_reply_to: the original offer
    """

    as_object: VulnerabilityCaseRef = Field(None, alias="object")
    in_reply_to: OfferCaseOwnershipTransfer | str | None = None


class RejectCaseOwnershipTransfer(as_Reject):
    """The actor is rejecting an offer to transfer ownership of the case.
    as_object: VulnerabilityCase
    context: the original offer
    """

    as_object: VulnerabilityCaseRef = Field(None, alias="object")
    in_reply_to: OfferCaseOwnershipTransfer | str | None = None


class RmInviteToCase(as_Invite):
    """The actor is inviting another actor to a case.
    This corresponds to the Vultron Message Type RS when a case already exists.
    See also RmSubmitReport for the scenario when a case does not exist yet.
    as_object: VulnerabilityCase
    """

    as_object: VulnerabilityCaseRef = Field(None, alias="object")


RmInviteToCaseRef: TypeAlias = ActivityStreamRef[RmInviteToCase]


class RmAcceptInviteToCase(as_Accept):
    """The actor is accepting an invitation to a case.
    This corresponds to the Vultron Message Type RV when the case already exists.
    See also RmValidateReport for the scenario when the case does not exist yet.
    as_object: VulnerabilityCase
    in_reply_to: RmInviteToCase
    """

    in_reply_to: RmInviteToCaseRef = None


class RmRejectInviteToCase(as_Reject):
    """The actor is rejecting an invitation to a case.
    This corresponds to the Vultron Message Type RI when the case already exists.
    See also RmInvalidateReport for the scenario when the case does not exist yet.

    `as_object`: `VulnerabilityCase`
    `in_reply_to`: `RmInviteToCase`
    """

    in_reply_to: RmInviteToCaseRef = None
