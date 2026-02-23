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

# TODO: remove Literals because parent classes already define them
# TODO: use pydantic's typing more effectively

from pydantic import Field, model_validator

from vultron.as_vocab.base.objects.activities.transitive import (
    as_Add,
    as_Create,
    as_Remove,
)
from vultron.as_vocab.base.utils import name_of
from vultron.as_vocab.objects.case_participant import CaseParticipantRef
from vultron.as_vocab.objects.case_status import ParticipantStatusRef
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCaseRef


class CreateParticipant(as_Create):
    """Create a new CaseParticipant"""

    as_object: CaseParticipantRef = Field(None, alias="object")
    target: VulnerabilityCaseRef = None

    @model_validator(mode="after")
    def set_name(self):
        """Override default name to clearly identify CaseParticipant creation.

        Produces a name of the form:
            "{actor} Create CaseParticipant {participant_id} from {attributed_to} in {case_id}"
        making it obvious that a participant object is being created for an actor,
        not the actor itself.
        """
        if self.name is not None:
            return self

        parts = []
        if self.actor is not None:
            parts.append(name_of(self.actor))
        parts.append("Create CaseParticipant")
        if self.as_object is not None:
            participant_id = getattr(self.as_object, "as_id", None)
            if participant_id:
                parts.append(str(participant_id))
            attributed_to = getattr(self.as_object, "attributed_to", None)
            if attributed_to:
                parts.extend(["from", str(attributed_to)])
        if self.context is not None:
            parts.extend(["in", str(self.context)])

        if parts:
            self.name = " ".join(parts)
        return self


class CreateStatusForParticipant(as_Create):
    """Create a new CaseStatus for a CaseParticipant"""

    as_object: ParticipantStatusRef = Field(None, alias="object")
    target: CaseParticipantRef = None


# add CaseStatus to CaseParticipant
class AddStatusToParticipant(as_Add):
    """Add a CaseStatus to a CaseParticipant
    as_object: CaseStatus
    target: CaseParticipant
    """

    as_object: ParticipantStatusRef = Field(None, alias="object")
    target: CaseParticipantRef = None


class AddParticipantToCase(as_Add):
    """Add a CaseParticipant to a VulnerabilityCase
    as_object: CaseParticipant
    target: VulnerabilityCase
    """

    as_object: CaseParticipantRef = Field(None, alias="object")
    target: VulnerabilityCaseRef = None


class RemoveParticipantFromCase(as_Remove):
    """Remove a CaseParticipant from a VulnerabilityCase.
    This should only be performed by the case owner.
    as_object: CaseParticipant
    origin: VulnerabilityCase
    """

    as_object: CaseParticipantRef = Field(None, alias="object")
    origin: VulnerabilityCaseRef = None
