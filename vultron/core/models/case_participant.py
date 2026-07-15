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

"""Domain representation of a case participant and role subclasses.

``CaseParticipant`` is the canonical core type.  ``VultronParticipant`` is
kept as a backward-compatibility alias.

Several convenience subclasses are provided that auto-set ``case_roles`` via
model validators:

- :class:`FinderParticipant`
- :class:`ReporterParticipant`
- :class:`FinderReporterParticipant`
- :class:`VendorParticipant`
- :class:`DeployerParticipant`
- :class:`CoordinatorParticipant`
- :class:`OtherParticipant`
- :class:`CaseActorParticipant`
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import Field, field_serializer, field_validator, model_validator

from vultron.core.models.base import CoreObject, NonEmptyString
from vultron.core.models.participant_status import (
    ParticipantStatus,
    coerce_cvd_roles,
    coerce_em_consent_state,
)
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.states.rm import RM, is_valid_rm_transition
from vultron.enums.roles import CVDRole, serialize_roles, validate_roles

logger = logging.getLogger(__name__)


class CaseParticipant(CoreObject):
    """Domain representation of a case participant.

    Canonical core type that mirrors the Vultron-specific fields of the wire
    ``CaseParticipant`` class and all its role subclasses.

    ``type_`` is ``Literal["CaseParticipant"]`` so this class auto-registers
    in :data:`CORE_VOCABULARY` and round-trips through the DataLayer.

    Role-specific subclasses (:class:`FinderParticipant`,
    :class:`VendorParticipant`, etc.) inherit from this class and auto-set
    ``case_roles`` via model validators.  All subclasses share the same
    ``type_`` value ``"CaseParticipant"`` because they carry no additional
    wire-level type discrimination.
    """

    type_: Literal["CaseParticipant"] = Field(
        default="CaseParticipant",
        validation_alias="type",
        serialization_alias="type",
    )
    case_roles: list[CVDRole] = Field(default_factory=list)
    participant_statuses: list[ParticipantStatus] = Field(default_factory=list)
    accepted_embargo_ids: list[NonEmptyString] = Field(default_factory=list)
    embargo_consent_state: PEC = Field(default=PEC.NO_EMBARGO)
    participant_case_name: NonEmptyString | None = None

    @field_serializer("case_roles")
    def _serialize_case_roles(self, value: list[CVDRole]) -> list[str]:
        return serialize_roles(value)

    @field_validator("case_roles", mode="before")
    @classmethod
    def _validate_case_roles(cls, value: object) -> list[CVDRole]:
        return validate_roles(value)

    @model_validator(mode="after")
    def _set_name_if_empty(self) -> CaseParticipant:
        """If ``name`` is unset, derive it from ``attributed_to``."""
        if self.name is not None:
            return self
        if self.attributed_to is None:
            return self
        self.name = self.attributed_to
        return self

    @model_validator(mode="after")
    def _init_participant_status_if_empty(self) -> CaseParticipant:
        """Seed ``participant_statuses`` with a default entry when empty."""
        if self.participant_statuses:
            return self
        self.participant_statuses = [
            ParticipantStatus(
                context=self.context or self.id_,
                attributed_to=self.attributed_to,
                em_consent_state=coerce_em_consent_state(
                    self.embargo_consent_state
                ),
                cvd_role=coerce_cvd_roles(self.case_roles),
            ),
        ]
        return self

    def _sync_latest_status_metadata(self) -> None:
        if not self.participant_statuses:
            return
        latest = self.participant_statuses[-1]
        latest.cvd_role = coerce_cvd_roles(self.case_roles)
        latest.em_consent_state = coerce_em_consent_state(
            self.embargo_consent_state
        )

    @property
    def participant_status(self) -> ParticipantStatus | None:
        """Return the most recently appended :class:`ParticipantStatus`.

        Uses list-index order (``[-1]``) rather than timestamp comparison to
        avoid clock-skew artefacts (see bug #659 on the wire layer).
        """
        if not self.participant_statuses:
            return None
        return self.participant_statuses[-1]

    def append_rm_state(self, rm_state: RM, actor: str, context: str) -> bool:
        """Append a new ParticipantStatus with the given RM state.

        Validates the transition against the RM state machine.  Skips the
        append (with a WARNING) when the transition is not valid.

        Args:
            rm_state: Target RM state.
            actor: URI of the actor asserting the transition.
            context: URI of the case context.

        Returns:
            ``True`` when the status was appended, ``False`` when blocked.
        """
        current = (
            self.participant_statuses[-1].rm_state
            if self.participant_statuses
            else RM.START
        )
        if not is_valid_rm_transition(current, rm_state):
            logger.warning(
                "Invalid RM transition %s → %s for participant %s; skipping",
                current,
                rm_state,
                self.id_,
            )
            return False
        self.participant_statuses.append(
            ParticipantStatus(
                rm_state=rm_state,
                context=context,
                attributed_to=actor,
                em_consent_state=coerce_em_consent_state(
                    self.embargo_consent_state
                ),
                cvd_role=coerce_cvd_roles(self.case_roles),
            )
        )
        return True

    def add_role(
        self, role: CVDRole, raise_when_present: bool = False
    ) -> None:
        """Add a role to the participant.

        Idempotent when role already exists.  Raises :exc:`KeyError` when
        ``raise_when_present=True`` and the role is already present.

        Args:
            role: CVD role to add.
            raise_when_present: when ``True``, raise :exc:`KeyError` if the
                role is already held.

        Raises:
            KeyError: when ``raise_when_present`` is ``True`` and the role is
                already present.
        """
        roles = set(self.case_roles)
        if role not in roles:
            roles.add(role)
        else:
            logger.info(
                "Attempted to add role %s to participant %s, but role was already present",
                role,
                self,
            )
            if raise_when_present:
                raise KeyError(
                    f"Role {role} was already present in participant.case_roles"
                )
        self.case_roles = list(roles)
        self._sync_latest_status_metadata()

    def remove_role(
        self, role: CVDRole, raise_when_missing: bool = False
    ) -> None:
        """Remove a role from the participant.

        Idempotent when role does not exist.  Raises :exc:`KeyError` when
        ``raise_when_missing=True`` and the role is not held.

        Args:
            role: CVD role to remove.
            raise_when_missing: when ``True``, raise :exc:`KeyError` if the
                role is not present.

        Raises:
            KeyError: when ``raise_when_missing`` is ``True`` and the role is
                not present.
        """
        roles = set(self.case_roles)
        if role in roles:
            roles.remove(role)
        else:
            logger.info(
                "Attempted to remove role %s from participant %s, but role was not present",
                role,
                self,
            )
            if raise_when_missing:
                raise KeyError(
                    f"Role {role} was not present to delete from participant.case_roles"
                )
        self.case_roles = list(roles)
        self._sync_latest_status_metadata()

    def has_role(self, role: CVDRole) -> bool:
        """Return ``True`` when the participant holds the given role."""
        return role in self.case_roles

    @property
    def roles(self) -> list[CVDRole]:
        """Return the participant's current CVD roles as a read-only copy."""
        return list(self.case_roles)


# ---------------------------------------------------------------------------
# Role subclasses
# ---------------------------------------------------------------------------


class FinderParticipant(CaseParticipant):
    """A CaseParticipant that holds the FINDER role."""

    @model_validator(mode="after")
    def _set_role(self) -> FinderParticipant:
        self.case_roles = []
        self.add_role(CVDRole.FINDER)
        return self


class ReporterParticipant(CaseParticipant):
    """A CaseParticipant that holds the REPORTER role.

    Also initialises ``participant_statuses`` to ``[ACCEPTED]`` because a
    reporter has by definition accepted the report.
    """

    @model_validator(mode="after")
    def _set_role(self) -> ReporterParticipant:
        self.case_roles = []
        self.add_role(CVDRole.REPORTER)
        return self

    @model_validator(mode="after")
    def _set_accepted_status(self) -> ReporterParticipant:
        self.participant_statuses = [
            ParticipantStatus(
                context=self.context or self.id_,
                attributed_to=self.attributed_to,
                rm_state=RM.ACCEPTED,
                em_consent_state=coerce_em_consent_state(
                    self.embargo_consent_state
                ),
                cvd_role=coerce_cvd_roles(self.case_roles),
            )
        ]
        return self


class FinderReporterParticipant(CaseParticipant):
    """A CaseParticipant that holds both FINDER and REPORTER roles.

    Also initialises ``participant_statuses`` to ``[ACCEPTED]``.
    """

    @model_validator(mode="after")
    def _set_roles(self) -> FinderReporterParticipant:
        self.case_roles = []
        self.add_role(CVDRole.FINDER)
        self.add_role(CVDRole.REPORTER)
        return self

    @model_validator(mode="after")
    def _set_accepted_status(self) -> FinderReporterParticipant:
        self.participant_statuses = [
            ParticipantStatus(
                context=self.context or self.id_,
                attributed_to=self.attributed_to,
                rm_state=RM.ACCEPTED,
                em_consent_state=coerce_em_consent_state(
                    self.embargo_consent_state
                ),
                cvd_role=coerce_cvd_roles(self.case_roles),
            )
        ]
        return self


class VendorParticipant(CaseParticipant):
    """A CaseParticipant that holds the VENDOR role."""

    @model_validator(mode="after")
    def _set_role(self) -> VendorParticipant:
        self.case_roles = []
        self.add_role(CVDRole.VENDOR)
        return self


class DeployerParticipant(CaseParticipant):
    """A CaseParticipant that holds the DEPLOYER role."""

    @model_validator(mode="after")
    def _set_role(self) -> DeployerParticipant:
        self.case_roles = []
        self.add_role(CVDRole.DEPLOYER)
        return self


class CoordinatorParticipant(CaseParticipant):
    """A CaseParticipant that holds the COORDINATOR role."""

    @model_validator(mode="after")
    def _set_role(self) -> CoordinatorParticipant:
        self.case_roles = []
        self.add_role(CVDRole.COORDINATOR)
        return self


class OtherParticipant(CaseParticipant):
    """A CaseParticipant that holds the OTHER role."""

    @model_validator(mode="after")
    def _set_role(self) -> OtherParticipant:
        self.case_roles = []
        self.add_role(CVDRole.OTHER)
        return self


class CaseActorParticipant(CaseParticipant):
    """A participant that acts as the CaseActor service for a VulnerabilityCase.

    Holds both ``COORDINATOR`` and ``CASE_MANAGER`` roles (CBT-01-003).
    The ``attributed_to`` field identifies the ActivityStreams Service URI
    that will send ``Announce(VulnerabilityCase)`` updates on behalf of the
    case owner.  Receivers use this participant to establish trusted CaseActor
    identity during bootstrap.
    """

    @model_validator(mode="after")
    def _set_role(self) -> CaseActorParticipant:
        self.case_roles = []
        self.add_role(CVDRole.COORDINATOR)
        self.add_role(CVDRole.CASE_MANAGER)
        return self


# ---------------------------------------------------------------------------
# Backward-compatibility alias
# ---------------------------------------------------------------------------

#: Alias kept for backward compatibility.  New code should import
#: :class:`CaseParticipant` directly.
VultronParticipant = CaseParticipant
