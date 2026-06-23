"""Wire-layer vocabulary type for the CaseProposal protocol.

Provides :class:`as_CaseProposal`, the AS2 Object type used in the
``Create(as_CaseProposal)`` / ``Accept(as_CaseProposal)`` /
``Reject(as_CaseProposal)`` message flow defined in ADR-0023.

Spec: ``specs/case-proposal.yaml`` CP-01-001 through CP-01-006.
"""

# pyright: reportGeneralTypeIssues=false
# Rationale: as_CaseProposal narrows several optional base-class fields to
# required.  Black wraps the Field() calls across multiple lines, making
# inline pyright-ignore comments unreliable (see notes/codebase-structure.md
# § "Black Can Invalidate Inline pyright Suppressions on Wrapped Fields").

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

from pydantic import Field

from vultron.core.models.base import NonEmptyString
from vultron.core.models.enums import VultronObjectType as VO_type
from vultron.wire.as2.vocab.base.links import ActivityStreamRef
from vultron.wire.as2.vocab.objects.base import VultronAS2Object
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)


class as_CaseProposal(VultronAS2Object):
    """Wire representation of a CaseProposal object (CP-01-001).

    A vendor actor creates this object to request that a dedicated
    case-actor service initialise a new :class:`VulnerabilityCase`.
    The case-actor evaluates the proposal and responds with either
    ``Accept(as_CaseProposal)`` followed by
    ``Create(VulnerabilityCase)`` (happy path, CP-05-003) or
    ``Reject(as_CaseProposal)`` (rejection path, CP-05-004).

    All classes in ``vultron/wire/as2/vocab/objects/`` use the ``as_``
    prefix (ARCH-14-001); the bare name ``CaseProposal`` is reserved for
    any future core domain model.

    Fields:
        type_: Always ``"CaseProposal"``; registered in ``VultronObjectType``.
        attributed_to: Required URI of the vendor actor that originated
            the proposal (CP-01-003).
        object_: Required inline ``VulnerabilityReport`` around which the
            case is to be created.  URI-only references are not permitted
            (CP-01-004, AKM-03-001).
        target: Required URI of the prospective case-actor service to
            which the proposal is addressed (CP-01-005).
        summary: Optional human-readable description of the proposal
            (CP-01-006).
    """

    type_: VO_type = Field(
        default=VO_type.CASE_PROPOSAL,
        validation_alias="type",
        serialization_alias="type",
    )

    # CP-01-003: vendor actor URI that originated the proposal.
    attributed_to: NonEmptyString = Field(
        ...,
        description="URI of the vendor actor that originated the proposal.",
    )

    # CP-01-004: fully inline VulnerabilityReport; URI references not permitted.
    object_: VulnerabilityReport = Field(
        ...,
        validation_alias="object",
        serialization_alias="object",
        description="Inline VulnerabilityReport; URI-only refs not permitted (AKM-03-001).",
    )

    # CP-01-005: URI of the prospective case-actor service.
    target: NonEmptyString = Field(
        ...,
        description="URI of the prospective case-actor service.",
    )

    # CP-01-006: optional human-readable summary.
    # summary is inherited as Any|None from as_Object; narrowed here.
    summary: NonEmptyString | None = Field(
        default=None,
        description="Optional human-readable description of the proposal.",
    )


as_CaseProposalRef: TypeAlias = ActivityStreamRef[as_CaseProposal]
