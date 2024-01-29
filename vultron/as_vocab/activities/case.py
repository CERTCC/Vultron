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
Custom Activity Streams Activities for VulnerabilityCase objects.
Each activity should have a VulnerabilityCase object as either its target or object.
"""

from dataclasses import dataclass, field
from typing import Optional

from dataclasses_json import LetterCase, config, dataclass_json

from vultron.as_vocab.base.links import as_Link
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
from vultron.as_vocab.base.objects.actors import as_Actor
from vultron.as_vocab.base.objects.object_types import as_Note
from vultron.as_vocab.base.utils import exclude_if_none
from vultron.as_vocab.objects.case_status import CaseStatus
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport


########################################################################################
# Activities in which the VulnerabilityCase is a target
########################################################################################


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class AddReportToCase(as_Add):
    """Add a VulnerabilityReport to a VulnerabilityCase
    as_object: VulnerabilityReport
    target: VulnerabilityCase
    """

    as_type: str = field(default="Add", init=False)
    as_object: Optional[VulnerabilityReport | as_Link | str] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )
    target: Optional[VulnerabilityCase | as_Link | str] = field(default=None)


# add CaseParticipant to VulnerabilityCase
# see AddParticipantToCase in case_participant.py


# add CaseStatus to VulnerabilityCase
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class AddStatusToCase(as_Add):
    """Add a CaseStatus to a VulnerabilityCase.
    This should only be performed by the case owner.
    Other case participants can add a case status to their participant record, which the case
    owner should then add to the case if appropriate.
    as_object: CaseStatus
    target: VulnerabilityCase
    """

    as_type: str = field(default="Add", init=False)
    as_object: Optional[CaseStatus | as_Link | str] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )
    target: Optional[VulnerabilityCase | as_Link | str] = field(default=None)


########################################################################################
# Activities in which the VulnerabilityCase is an object #
########################################################################################


# create a VulnerabilityCase
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class CreateCase(as_Create):
    """Create a VulnerabilityCase.
    as_object: VulnerabilityCase
    """

    as_type: str = field(default="Create", init=False)
    as_object: Optional[VulnerabilityCase | as_Link | str] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class CreateCaseStatus(as_Create):
    """Create a CaseStatus.
    as_object: CaseStatus
    """

    as_type: str = field(default="Create", init=False)
    as_object: Optional[CaseStatus | as_Link | str] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )


# Add a Note to a VulnerabilityCase
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class AddNoteToCase(as_Add):
    """Add a Note to a VulnerabilityCase.
    as_object: Note
    target: VulnerabilityCase
    """

    as_type: str = field(default="Add", init=False)
    as_object: Optional[as_Note | as_Link | str] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )
    target: Optional[VulnerabilityCase | as_Link | str] = field(default=None)


# update a VulnerabilityCase
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class UpdateCase(as_Update):
    """Update a VulnerabilityCase.
    as_object: VulnerabilityCase
    """

    as_type: str = field(default="Update", init=False)
    as_object: Optional[VulnerabilityCase | as_Link | str] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )


#####
# Custom Activity Streams Activities specific to the Vultron Protocol
#####


# join a case
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class RmEngageCase(as_Join):
    """The actor is has joined (i.e., is actively working on) a case.
    This represents the Vultron Message Type RA, and indicates that the actor is now in the RM.ACCEPTED state.
    as_object: VulnerabilityCase
    """

    as_type: str = field(default="Join", init=False)
    as_object: Optional[VulnerabilityCase | as_Link | str] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class RmDeferCase(as_Ignore):
    """The actor is deferring a case.
    This implies that the actor is no longer actively working on the case.
    Deferring a case does not imply that the actor is abandoning the case entirely,
    it just means that the actor is no longer actively working on it.
    This represents the Vultron Message Type RD, and indicates that the actor is now in the RM.DEFERRED state.
    Contrast with RmCloseCase, which indicates that the actor is abandoning the case entirely.
    as_object: VulnerabilityCase
    """

    as_type: str = field(default="Ignore", init=False)
    as_object: Optional[VulnerabilityCase | as_Link | str] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class RmCloseCase(as_Leave):
    """The actor is ending their participation in the case and closing their local copy of the case.
    This corresponds to the Vultron RC message type.
    Case closure is considered a permanent Leave from the case.
    If the case owner (attributedTo) is the actor, then the case is closed for all participants.
    If the actor is not the case owner, then the actor should be removed from the case participants.
    as_object: VulnerabilityCase
    """

    as_type: str = field(default="Leave", init=False)
    as_object: Optional[VulnerabilityCase | as_Link | str] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class OfferCaseOwnershipTransfer(as_Offer):
    """The actor is offering to transfer ownership of the case to another actor.
    as_object: VulnerabilityCase
    target: as_Actor
    """

    as_type: str = field(default="Offer", init=False)
    as_object: Optional[VulnerabilityCase | as_Link | str] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )
    target: Optional[as_Actor | as_Link | str] = field(
        metadata=config(exclude=exclude_if_none), default=None
    )


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class AcceptCaseOwnershipTransfer(as_Accept):
    """The actor is accepting an offer to transfer ownership of the case.

    - as_object: VulnerabilityCase
    - in_reply_to: the original offer
    """

    as_type: str = field(default="Accept", init=False)
    as_object: Optional[VulnerabilityCase | as_Link | str] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )
    in_reply_to: OfferCaseOwnershipTransfer = field(
        default=None,
    )


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class RejectCaseOwnershipTransfer(as_Reject):
    """The actor is rejecting an offer to transfer ownership of the case.
    as_object: VulnerabilityCase
    context: the original offer
    """

    as_type: str = field(default="Reject", init=False)
    as_object: Optional[VulnerabilityCase | as_Link | str] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )
    in_reply_to: OfferCaseOwnershipTransfer = field(
        default=None,
    )


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class RmInviteToCase(as_Invite):
    """The actor is inviting another actor to a case.
    This corresponds to the Vultron Message Type RS when a case already exists.
    See also RmSubmitReport for the scenario when a case does not exist yet.
    as_object: VulnerabilityCase
    """

    as_type: str = field(default="Invite", init=False)
    as_object: Optional[VulnerabilityCase | as_Link | str] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class RmAcceptInviteToCase(as_Accept):
    """The actor is accepting an invitation to a case.
    This corresponds to the Vultron Message Type RV when the case already exists.
    See also RmValidateReport for the scenario when the case does not exist yet.
    as_object: VulnerabilityCase
    in_reply_to: RmInviteToCase
    """

    as_type: str = field(default="Accept", init=False)
    as_object: Optional[VulnerabilityCase | as_Link | str] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )
    in_reply_to: RmInviteToCase = field(default=None)


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class RmRejectInviteToCase(as_Reject):
    """The actor is rejecting an invitation to a case.
    This corresponds to the Vultron Message Type RI when the case already exists.
    See also RmInvalidateReport for the scenario when the case does not exist yet.

    `as_object`: `VulnerabilityCase`
    `in_reply_to`: `RmInviteToCase`
    """

    as_type: str = field(default="Reject", init=False)
    as_object: Optional[VulnerabilityCase | as_Link | str] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )
    in_reply_to: RmInviteToCase = field(default=None)
