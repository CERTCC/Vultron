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

from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Add,
    as_Create,
    as_Remove,
)
from vultron.wire.as2.vocab.base.utils import name_of
from vultron.wire.as2.vocab.objects.case_participant import (
    CaseParticipant,
    CaseParticipantRef,
)
from vultron.wire.as2.vocab.objects.case_status import (
    ParticipantStatus,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    VulnerabilityCaseRef,
)


class _CreateParticipantActivity(as_Create):
    """Create a new CaseParticipant"""

    object_: CaseParticipant = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
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
        participant_id = getattr(self.object_, "id_", None)
        if participant_id:
            parts.append(str(participant_id))
        attributed_to = getattr(self.object_, "attributed_to", None)
        if attributed_to:
            parts.extend(["from", str(attributed_to)])
        if self.context is not None:
            parts.extend(["in", str(self.context)])

        if parts:
            self.name = " ".join(parts)
        return self


class _CreateStatusForParticipantActivity(as_Create):
    """Create a new CaseStatus for a CaseParticipant"""

    object_: ParticipantStatus = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
    target: CaseParticipantRef = None


# add CaseStatus to CaseParticipant
class _AddStatusToParticipantActivity(as_Add):
    """Add a CaseStatus to a CaseParticipant
    object_: CaseStatus
    target: CaseParticipant
    """

    object_: ParticipantStatus = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
    target: CaseParticipantRef = None


class _AddParticipantToCaseActivity(as_Add):
    """Add a CaseParticipant to a VulnerabilityCase
    object_: CaseParticipant
    target: VulnerabilityCase
    """

    object_: CaseParticipant = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
    target: VulnerabilityCaseRef = None


class _RemoveParticipantFromCaseActivity(as_Remove):
    """Remove a CaseParticipant from a VulnerabilityCase.
    This should only be performed by the case owner.
    object_: CaseParticipant
    target: VulnerabilityCase
    """

    object_: CaseParticipant = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
    target: VulnerabilityCaseRef = None
