#!/usr/bin/env python

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

"""The participant-suggestion port's question and answer (ADR-0186, BT-24).

- :class:`SuggestionContext` is what the port is asked about: a profile of
  the case (:class:`~vultron.core.models.profile.ModelProfile`), built only by
  :meth:`SuggestionContext.from_case`.  It carries the reports' descriptive
  content as the evidence, since a report may name a vendor or product not
  yet in the case, and the participants, each with its actor id and roles
  only, as who is already included (BT-24-002, BT-24-003, BT-24-009).
- :class:`ParticipantSuggestion` is one answer: an actor id, a suggested
  role and the reason, and no timing (BT-24-004, BT-24-006).

What the context carries is a disclosure decision: everything in it leaves
the actor when the port's adapter calls an outside service.  Widening it is
a change to this module, which is the point (BT-24-003).
"""

from __future__ import annotations

from typing import Any, Final, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    model_validator,
)

from vultron.core.models.base import ValidatedAssignmentMixin
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.profile import ModelProfile
from vultron.core.models.report import VulnerabilityReport
from vultron.enums import CVDRole
from vultron.errors import VultronValidationError
from vultron.primitives import NonEmptyString

#: The validation-context key :meth:`SuggestionContext.from_case` sets; a
#: context built any other way lacks it and is refused (BT-24-003).
_PROJECTION_KEY: Final[str] = "_vultron_suggestion_projection"


class ReportProfile(ModelProfile):
    """A report's descriptive content, the evidence a suggester reads.

    Attributes:
        id_: The report's id.
        name: The report's title, if it has one.
        summary: The report's summary, if it has one.
        content: The report's body text, if it has one.
    """

    profile_of = VulnerabilityReport

    id_: NonEmptyString
    name: NonEmptyString | None = None
    summary: NonEmptyString | None = None
    content: NonEmptyString | None = None


class ParticipantProfile(ModelProfile):
    """One participant already in the case: its actor and roles only.

    Attributes:
        attributed_to: The participant's actor id.  Required: a participant
            with no actor names nobody to leave out of a suggestion.
        case_roles: The roles the participant holds in the case.
    """

    profile_of = CaseParticipant

    attributed_to: NonEmptyString
    case_roles: list[CVDRole] = Field(default_factory=list)


class SuggestionContext(ModelProfile):
    """The case, narrowed to what a participant suggester may see.

    Built only by :meth:`from_case`: constructing one directly, or
    validating a mapping as one, is refused, so the projection is defined
    once (BT-24-003).  Every field has the name and type of a field of
    :class:`~vultron.core.models.case.VulnerabilityCase` or of an object the
    case holds (BT-24-009).

    Attributes:
        id_: The case's id, so an adapter can tell one case from another.
        vulnerability_reports: Each report's descriptive content.
        case_participants: Who is already in the case.
    """

    profile_of = VulnerabilityCase

    id_: NonEmptyString
    vulnerability_reports: list[ReportProfile] = Field(default_factory=list)
    case_participants: list[ParticipantProfile] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _only_from_case(cls, data: Any, info: ValidationInfo) -> Any:
        """Refuse a context not built by :meth:`from_case` (BT-24-003)."""
        if not (info.context or {}).get(_PROJECTION_KEY):
            raise ValueError(
                "a SuggestionContext is built only by "
                "SuggestionContext.from_case(case) (BT-24-003)"
            )
        return data

    @classmethod
    def from_model(cls, source: BaseModel) -> Self:
        """Refused: the case is projected only by :meth:`from_case`.

        Raises:
            TypeError: Always.
        """
        raise TypeError(
            "SuggestionContext is projected only by "
            "SuggestionContext.from_case(case) (BT-24-003)."
        )

    @classmethod
    def from_case(cls, case: VulnerabilityCase) -> SuggestionContext:
        """Project *case* to the suggestion context (BT-24-003).

        The case must carry its reports and participants as objects: a bare
        reference has no content and no roles to project, and leaving it
        out would hide evidence or a party already in the case.  The core
        service
        (:func:`~vultron.core.services.participant_suggestion.suggest_case_participants`)
        resolves the references before it projects.

        Raises:
            VultronValidationError: A report or participant is a bare
                reference, or a participant names no actor.
        """
        bare = [
            ref
            for ref in (*case.vulnerability_reports, *case.case_participants)
            if isinstance(ref, str)
        ]
        if bare:
            raise VultronValidationError(
                f"VulnerabilityCase '{case.id_}' holds bare references "
                f"{bare}; the suggestion context projects the objects they "
                "name, so resolve them first (BT-24-003)."
            )
        return cls._build(
            {
                "id_": case.id_,
                "vulnerability_reports": [
                    ReportProfile.from_model(report)
                    for report in case.vulnerability_reports
                    if not isinstance(report, str)
                ],
                "case_participants": [
                    ParticipantProfile.from_model(participant)
                    for participant in case.case_participants
                    if not isinstance(participant, str)
                ],
            },
            case,
            context={_PROJECTION_KEY: True},
        )

    @property
    def vendors(self) -> list[ParticipantProfile]:
        """The case's current vendors: the participants holding VENDOR."""
        return [
            p for p in self.case_participants if CVDRole.VENDOR in p.case_roles
        ]


class ParticipantSuggestion(ValidatedAssignmentMixin):
    """One party the suggester thinks belongs in the case, and why.

    It names an identity and nothing about timing: whoever receives the
    suggestion schedules any invite, from the invitee's embargo policy and
    the case's remaining embargo (BT-24-006).

    Attributes:
        actor_id: The suggested actor's id.
        role: The CVD role the suggester thinks the actor holds.
        rationale: Why the suggester names this actor.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    actor_id: NonEmptyString
    role: CVDRole
    rationale: NonEmptyString


class ParticipantSuggestions(ValidatedAssignmentMixin):
    """The suggestions one ask of the port answered, as one typed value.

    The participant-suggestion Retriever's output port holds this rather
    than a bare ``list``, so the seam's type check on that port covers every
    suggestion, not just the container (BT-18-012, BTND-03-021).  It is
    empty by default: an answer naming nobody is valid (BT-24-004), and it
    is what a constant *yes* writes (BT-23-013).

    Attributes:
        suggestions: The suggestions, in the order the adapter gave them.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    suggestions: tuple[ParticipantSuggestion, ...] = ()


__all__ = [
    "ParticipantProfile",
    "ParticipantSuggestion",
    "ParticipantSuggestions",
    "ReportProfile",
    "SuggestionContext",
]
