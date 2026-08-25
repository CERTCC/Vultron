"""Wire-layer vocabulary type for the CaseParticipantRole object.

Provides :class:`as_CaseParticipantRole`, the AS2 Object type used in the
``Offer(CaseParticipantRole, target=Actor, context=VulnerabilityCase)``
role-delegation wire format defined in ADR-0039.

This type replaces the ambiguous ``Offer(VulnerabilityCase, target=CaseParticipant)``
format previously used for CASE_MANAGER role delegation. It generalises the
protocol to support offering any ``CVDRole`` to any Actor in a Case context.

Spec: ``specs/semantic-extraction.yaml`` SE-08-003.
ADR: ``docs/adr/0039-offer-case-participant-role-wire-type.md``.
"""

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

from typing import TypeAlias

from pydantic import Field, field_serializer, field_validator

from vultron.core.models.enums import VultronObjectType as VO_type
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.base.links import ActivityStreamRef
from vultron.wire.as2.vocab.objects.base import VultronAS2Object


class as_CaseParticipantRole(VultronAS2Object):
    """Wire representation of a CaseParticipantRole object (ADR-0039, SE-08-003).

    Carries a single ``CVDRole`` value to be offered to an Actor within a
    Case context.  The wire format is::

        Offer(CaseParticipantRole, target=Actor, context=VulnerabilityCase)

    This eliminates the structural ambiguity of the deprecated
    ``Offer(VulnerabilityCase, target=CaseParticipant)`` format and
    generalises role delegation beyond CASE_MANAGER.

    All classes in ``vultron/wire/as2/vocab/objects/`` use the ``as_``
    prefix (ARCH-14-001); the bare name ``CaseParticipantRole`` is reserved
    for any future core domain model.

    Fields:
        type_: Always ``"CaseParticipantRole"``; registered in
            ``VultronObjectType``.
        role: Required ``CVDRole`` being offered.
    """

    type_: VO_type = Field(
        default=VO_type.CASE_PARTICIPANT_ROLE,
        validation_alias="type",
        serialization_alias="type",
    )

    role: CVDRole = Field(
        ...,
        description="The CVDRole being offered to the target Actor.",
    )

    @field_serializer("role")
    def serialize_role(self, value: CVDRole) -> str:
        return str(value)

    @field_validator("role", mode="before")
    @classmethod
    def validate_role(cls, value: object) -> CVDRole:
        if isinstance(value, CVDRole):
            return value
        return CVDRole(str(value))


as_CaseParticipantRoleRef: TypeAlias = ActivityStreamRef[
    as_CaseParticipantRole
]
