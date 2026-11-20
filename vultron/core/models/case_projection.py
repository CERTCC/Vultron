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

"""A case cut for a projection, and what its call site passes (ADR-0219).

A renderer reads only a :class:`ProjectionCut` and the call site's
:class:`ProjectionInputs`, never the case or its ledger, so a renderer cannot
show what the profile withheld.  Nothing here names a format: a CSAF renderer
is the first that reads them, and a CVE record or a CERT Vulnerability Note
renderer reads the same two.

The cut carries the versioned name and distribution label of the profile
that made it (:meth:`ProjectionCut.of`), so a document cannot be labelled or
named by another profile than the one that decided what it holds.  The
inputs carry the rest:

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

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    InstanceOf,
    model_validator,
)

from vultron.core.models.base import NonEmptyString, ValidatedAssignmentMixin
from vultron.core.models.case.vulnerability_case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_preview import CasePreview
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


class _Value(ValidatedAssignmentMixin, BaseModel):
    """A value a call site passes beside a cut: a plain model, not an AS2
    object, because it never travels as one.  Frozen, so a renderer cannot
    change what its call site passed."""

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


class ProjectionCut(_Value):
    """A case and its ledger cut by one projection profile (ADR-0219).

    Built by :meth:`of`.  The cut holds the profile itself, and its name and
    label are read from it, so a document cannot be named by one profile and
    labelled by another.

    Attributes:
        preview: The cut.
        profile: The profile that cut it.
    """

    preview: CasePreview
    profile: InstanceOf[ProjectionProfile]

    @property
    def profile_name(self) -> str:
        """The versioned name of the profile that cut :attr:`preview`."""
        return self.profile.name

    @property
    def distribution(self) -> DistributionLabel:
        """The label every document of the cut is shared under."""
        return self.profile.distribution

    @classmethod
    def of(
        cls,
        case: VulnerabilityCase,
        ledger: Sequence[CaseLedgerEntry],
        profile: ProjectionProfile,
    ) -> ProjectionCut:
        """Cut *case* and its *ledger* by *profile*.

        Raises:
            VultronActivityConstructionError: When a substitution cannot be
                made (:meth:`~vultron.core.models.case_preview.CasePreview.
                for_projection`).
        """
        return cls(
            preview=CasePreview.for_projection(case, ledger, profile),
            profile=profile,
        )


class ProjectionInputs(_Value):
    """What a projection's call site passes beside the cut (ADR-0219).

    Attributes:
        status: The call site's publication status.
        projecting_actor: The publisher.
        position_committed_at: The commit time of the ledger entry at the
            preview's position: every date the document's tracking states.
        caller_acknowledgments: The credit the caller supplies; ``None`` when
            it supplies none, which is distinct from an empty list, a caller
            that credits no one.
        default_acknowledgments: The call site's default when the caller
            supplies none (:func:`reporter_acknowledgments`).
    """

    status: PublicationStatus
    projecting_actor: ProjectingActor
    position_committed_at: AwareDatetime
    caller_acknowledgments: tuple[Acknowledgment, ...] | None = None
    default_acknowledgments: tuple[Acknowledgment, ...] = ()

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
    "ProjectionCut",
    "ProjectionInputs",
    "PublicationStatus",
    "reporter_acknowledgments",
]
