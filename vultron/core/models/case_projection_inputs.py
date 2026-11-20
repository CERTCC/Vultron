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

"""What a projection's call site passes beside the cut preview (ADR-0219).

A renderer reads only the preview and these inputs, never the case or its
ledger, so a renderer cannot show what the profile withheld.  Nothing here
names a format: a CSAF renderer is the first that reads them, and a CVE
record or a CERT Vulnerability Note renderer reads the same inputs.

- The profile's versioned name and its distribution label
  (:class:`~vultron.core.models.case_projection_profile.ProjectionProfile`).
- The call site's publication status: ``final`` at publication, ``interim``
  for the operator's coordination document.
- The projecting actor, who publishes the document, and the roles it holds.
- The commit time of the ledger entry at the preview's position, which every
  document date is, so the same inputs give the same document (ADR-0176).
- The acknowledgments.  A case records no public credit (ADR-0218), so a
  projection takes them from its caller, or, when the caller supplies none,
  from the default its call site derives: the participants that hold the
  ``REPORTER`` role (:func:`reporter_acknowledgments`).
"""

from collections.abc import Sequence
from enum import StrEnum
from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, model_validator

from vultron.core.models.base import NonEmptyString
from vultron.core.models.case.vulnerability_case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_projection_profile import (
    DistributionLabel,
    ProjectionProfile,
)
from vultron.enums.roles import CVDRole


class PublicationStatus(StrEnum):
    """How settled a projected document is, as its call site fixes it."""

    DRAFT = "draft"
    INTERIM = "interim"
    FINAL = "final"


class _Value(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ProjectingActor(_Value):
    """The actor that makes a projection: the document's publisher.

    Attributes:
        id_: The actor's id, a URI.
        name: The actor's name.
        roles: The participant roles it holds in the case, in the order the
            case lists them.
    """

    id_: NonEmptyString
    name: NonEmptyString
    roles: tuple[CVDRole, ...] = ()


class Acknowledgment(_Value):
    """One party a projection credits, in the shape a credit list takes.

    Raises:
        ValueError: When it names no one and says nothing: a credit that
            credits nobody.
    """

    names: tuple[NonEmptyString, ...] = ()
    organization: NonEmptyString | None = None
    summary: NonEmptyString | None = None

    @model_validator(mode="after")
    def _credits_someone(self) -> Self:
        if not (self.names or self.organization or self.summary):
            raise ValueError(
                "an acknowledgment names someone, an organization or why"
                " (ADR-0218)"
            )
        return self


class ProjectionInputs(_Value):
    """What a projection's call site passes beside the preview (ADR-0219).

    Attributes:
        profile_name: The versioned name of the profile that cut the preview.
        distribution: The label the document is shared under.
        status: The call site's publication status.
        projecting_actor: The publisher.
        position_committed_at: The commit time of the ledger entry at the
            preview's position: every date the document states.
        caller_acknowledgments: The credit the caller supplies; ``None`` when
            it supplies none, which is distinct from an empty list, a caller
            that credits no one.
        default_acknowledgments: The call site's default when the caller
            supplies none (:func:`reporter_acknowledgments`).
    """

    profile_name: NonEmptyString
    distribution: DistributionLabel
    status: PublicationStatus
    projecting_actor: ProjectingActor
    position_committed_at: AwareDatetime
    caller_acknowledgments: tuple[Acknowledgment, ...] | None = None
    default_acknowledgments: tuple[Acknowledgment, ...] = ()

    @classmethod
    def for_profile(
        cls,
        profile: ProjectionProfile,
        *,
        status: PublicationStatus,
        projecting_actor: ProjectingActor,
        position_committed_at: AwareDatetime,
        caller_acknowledgments: Sequence[Acknowledgment] | None = None,
        default_acknowledgments: Sequence[Acknowledgment] = (),
    ) -> ProjectionInputs:
        """The inputs of a projection cut by *profile*: its name and label,
        and what the call site passes."""
        return cls(
            profile_name=profile.name,
            distribution=profile.distribution,
            status=status,
            projecting_actor=projecting_actor,
            position_committed_at=position_committed_at,
            caller_acknowledgments=(
                None
                if caller_acknowledgments is None
                else tuple(caller_acknowledgments)
            ),
            default_acknowledgments=tuple(default_acknowledgments),
        )

    @property
    def acknowledgments(self) -> tuple[Acknowledgment, ...]:
        """The credit the document gives: the caller's, or else the call
        site's default (ADR-0218)."""
        if self.caller_acknowledgments is not None:
            return self.caller_acknowledgments
        return self.default_acknowledgments


def _reporter_name(participant: object) -> str | None:
    """The name a ``REPORTER`` participant is credited by: its own, else its
    actor's id; ``None`` for anything else."""
    if not isinstance(participant, CaseParticipant):
        return None
    if CVDRole.REPORTER not in participant.case_roles:
        return None
    return participant.name or participant.attributed_to


def reporter_acknowledgments(
    case: VulnerabilityCase,
) -> tuple[Acknowledgment, ...]:
    """The default credit of a projection of *case*: each participant that
    holds the ``REPORTER`` role, by its name, else its actor's id (ADR-0218).

    A participant the case holds only by id names no role, so it is not
    credited.  Nothing else in the case is read: the case records no credit.
    """
    names = (_reporter_name(p) for p in case.case_participants)
    return tuple(Acknowledgment(names=(name,)) for name in names if name)


__all__ = [
    "Acknowledgment",
    "ProjectingActor",
    "ProjectionInputs",
    "PublicationStatus",
    "reporter_acknowledgments",
]
