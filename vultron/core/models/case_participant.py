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
from typing import Any, Literal

from pydantic import Field, field_serializer, field_validator, model_validator

from vultron.core.models._helpers import _new_urn
from vultron.core.models._wire_spelling import reject_wire_spelled_keys
from vultron.core.models.base import CoreObject, NonEmptyString
from vultron.errors import VultronValidationError
from vultron.core.models.dimensions import PecDimension, RmDimension
from vultron.core.models.participant_status import (
    ParticipantStatus,
    coerce_cvd_roles,
    coerce_em_consent_state,
)
from vultron.core.states.participant_embargo_consent import PEC, PEC_Trigger
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

    @model_validator(mode="before")
    @classmethod
    def _reject_wire_spelled_keys(cls, data: Any) -> Any:
        """Raise on camelCase keys that Pydantic would silently discard.

        This class declares no ``alias_generator``, so a wire-spelled key such
        as ``participantStatuses`` is an *unknown* key.  Pydantic v2 ignores
        unknown keys by default, so it was silently dropped and
        ``_init_participant_status_if_empty`` then re-seeded a single status at
        ``RM.START``: a whole RM ladder vanished without a trace (issue #2232).
        The same drop applied to every other snake-only field on this model
        (``case_roles``, ``accepted_embargo_ids``, ``embargo_consent_state``,
        ``participant_case_name``), so roles could be lost the same way.

        Wire→core conversion belongs at the boundary
        (``as_CaseParticipant.to_core()``, which emits snake_case), not here.
        This validator makes the mismatch loud instead of lossy
        (ARCH-15-001, ARCH-15-002).

        Fields that declare an explicit camelCase ``validation_alias`` (e.g.
        ``in_reply_to``/``inReplyTo``) are sanctioned spellings and are
        accepted unchanged.

        **This guard is one level deep, by design and not by accident.** The
        nested :class:`ParticipantStatus` *does* set
        ``alias_generator=to_camel`` and accepts flat wire spellings
        (``rmState``) through its own migration shim, so
        ``{"participant_statuses": [{"rmState": "CLOSED"}]}`` is accepted here
        and yields ``rm.state == RM.CLOSED``.  That asymmetry is a known
        deviation from ARCH-12-003 tracked in #1991 — the child's shim is what
        makes this parent guard survivable in the first place — and it is not
        a hole in the #2232 fix: an aliased child cannot *lose* the ladder, it
        only spells it differently.  Do not restate ARCH-12-003 as though it
        held throughout this subtree; it does not yet.

        Raises:
            VultronValidationError: when a wire-spelled key is present.
        """
        return reject_wire_spelled_keys(
            cls, data, "as_CaseParticipant.to_core()"
        )

    @field_serializer("case_roles")
    def _serialize_case_roles(self, value: list[CVDRole]) -> list[str]:
        return serialize_roles(value)

    @field_validator("case_roles", mode="before")
    @classmethod
    def _validate_case_roles(cls, value: object) -> list[CVDRole]:
        return validate_roles(value)

    @model_validator(mode="before")
    @classmethod
    def _set_name_if_empty(cls, data: Any) -> Any:
        """If ``name`` is unset, derive it from ``attributed_to``."""
        if not isinstance(data, dict):
            return data
        name = data.get("name")
        attributed_to = data.get("attributed_to")
        if name is None and attributed_to is not None:
            data = dict(data)
            data["name"] = attributed_to
        return data

    @model_validator(mode="before")
    @classmethod
    def _init_participant_status_if_empty(cls, data: Any) -> Any:
        """Seed ``participant_statuses`` with a default entry when empty."""
        if not isinstance(data, dict):
            return data
        if data.get("participant_statuses"):
            return data
        data = dict(data)
        if not data.get("id") and not data.get("id_"):
            data["id"] = _new_urn()
        id_val = data.get("id") or data.get("id_")
        _consent_state = coerce_em_consent_state(
            data.get("embargo_consent_state", PEC.NO_EMBARGO)
        )
        data["participant_statuses"] = [
            ParticipantStatus(
                context=data.get("context") or id_val,
                attributed_to=data.get("attributed_to"),
                consent=(
                    PecDimension(state=_consent_state)
                    if _consent_state is not None
                    else None
                ),
                cvd_role=coerce_cvd_roles(data.get("case_roles") or []),
            ),
        ]
        return data

    def _sync_latest_status_metadata(self) -> None:
        if not self.participant_statuses:
            return
        latest = self.participant_statuses[-1]
        latest.cvd_role = coerce_cvd_roles(self.case_roles)
        _consent_state = coerce_em_consent_state(self.embargo_consent_state)
        latest.consent = (
            PecDimension(state=_consent_state)
            if _consent_state is not None
            else None
        )

    def apply_pec_transition(self, trigger: PEC_Trigger) -> None:
        """Apply *trigger* to the PEC state machine and sync ParticipantStatus.

        Uses ``PecDimension.transition()`` for fail-closed FSM validation
        (raises ``VultronInvalidStateTransitionError`` on an illegal trigger),
        then updates ``embargo_consent_state`` and syncs the latest
        ``ParticipantStatus.consent`` via ``_sync_latest_status_metadata()``.

        This is the single authoritative consent-write path (CM-18-005,
        CM-18-006, ADR-0048).  All sites that record a PEC change MUST call
        this method instead of assigning ``embargo_consent_state`` directly or
        using the ``apply_pec_trigger()`` helper.
        """
        current_pec = coerce_em_consent_state(self.embargo_consent_state)
        if current_pec is None:
            current_pec = PEC.NO_EMBARGO
        new_dim = PecDimension(state=current_pec).transition(trigger)
        self.embargo_consent_state = new_dim.state
        self._sync_latest_status_metadata()

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
            self.participant_statuses[-1].rm.state
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
        _consent_state = coerce_em_consent_state(self.embargo_consent_state)
        self.participant_statuses.append(
            ParticipantStatus(
                rm=RmDimension(state=rm_state),
                context=context,
                attributed_to=actor,
                consent=(
                    PecDimension(state=_consent_state)
                    if _consent_state is not None
                    else None
                ),
                cvd_role=coerce_cvd_roles(self.case_roles),
            )
        )
        return True

    def add_participant_status(self, status: ParticipantStatus) -> None:
        """Append a ParticipantStatus to this participant's history.

        Validates the appended item's shape and raises
        :exc:`~vultron.errors.VultronValidationError` when a non-core
        (wire-shaped) input is passed, closing the ``append`` door for
        ``participant_statuses`` (PRM-03-003, ADR-0064).

        Args:
            status: A core :class:`ParticipantStatus` object.

        Raises:
            VultronValidationError: when *status* is not a
                :class:`ParticipantStatus` instance.
        """
        if not isinstance(status, ParticipantStatus):
            raise VultronValidationError(
                f"add_participant_status expects a ParticipantStatus; "
                f"got {type(status).__name__}"
            )
        self.participant_statuses.append(status)

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

    @model_validator(mode="before")
    @classmethod
    def _set_role(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        roles = [CVDRole.FINDER]
        data["case_roles"] = roles
        ps_list = data.get("participant_statuses")
        if ps_list:
            latest = ps_list[-1]
            if isinstance(latest, ParticipantStatus):
                latest.cvd_role = coerce_cvd_roles(roles)
        return data


class ReporterParticipant(CaseParticipant):
    """A CaseParticipant that holds the REPORTER role.

    Also initialises ``participant_statuses`` to ``[ACCEPTED]`` because a
    reporter has by definition accepted the report.
    """

    @model_validator(mode="before")
    @classmethod
    def _set_role(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        roles = [CVDRole.REPORTER]
        data["case_roles"] = roles
        ps_list = data.get("participant_statuses")
        if ps_list:
            latest = ps_list[-1]
            if isinstance(latest, ParticipantStatus):
                latest.cvd_role = coerce_cvd_roles(roles)
        return data

    @model_validator(mode="before")
    @classmethod
    def _set_accepted_status(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        if not data.get("id") and not data.get("id_"):
            data["id"] = _new_urn()
        id_val = data.get("id") or data.get("id_")
        _consent_state = coerce_em_consent_state(
            data.get("embargo_consent_state", PEC.NO_EMBARGO)
        )
        data["participant_statuses"] = [
            ParticipantStatus(
                context=data.get("context") or id_val,
                attributed_to=data.get("attributed_to"),
                rm=RmDimension(state=RM.ACCEPTED),
                consent=(
                    PecDimension(state=_consent_state)
                    if _consent_state is not None
                    else None
                ),
                cvd_role=coerce_cvd_roles(data.get("case_roles") or []),
            )
        ]
        return data


class FinderReporterParticipant(CaseParticipant):
    """A CaseParticipant that holds both FINDER and REPORTER roles.

    Also initialises ``participant_statuses`` to ``[ACCEPTED]``.
    """

    @model_validator(mode="before")
    @classmethod
    def _set_roles(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        roles = [CVDRole.FINDER, CVDRole.REPORTER]
        data["case_roles"] = roles
        ps_list = data.get("participant_statuses")
        if ps_list:
            latest = ps_list[-1]
            if isinstance(latest, ParticipantStatus):
                latest.cvd_role = coerce_cvd_roles(roles)
        return data

    @model_validator(mode="before")
    @classmethod
    def _set_accepted_status(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        if not data.get("id") and not data.get("id_"):
            data["id"] = _new_urn()
        id_val = data.get("id") or data.get("id_")
        _consent_state = coerce_em_consent_state(
            data.get("embargo_consent_state", PEC.NO_EMBARGO)
        )
        data["participant_statuses"] = [
            ParticipantStatus(
                context=data.get("context") or id_val,
                attributed_to=data.get("attributed_to"),
                rm=RmDimension(state=RM.ACCEPTED),
                consent=(
                    PecDimension(state=_consent_state)
                    if _consent_state is not None
                    else None
                ),
                cvd_role=coerce_cvd_roles(data.get("case_roles") or []),
            )
        ]
        return data


class VendorParticipant(CaseParticipant):
    """A CaseParticipant that holds the VENDOR role."""

    @model_validator(mode="before")
    @classmethod
    def _set_role(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        roles = [CVDRole.VENDOR]
        data["case_roles"] = roles
        ps_list = data.get("participant_statuses")
        if ps_list:
            latest = ps_list[-1]
            if isinstance(latest, ParticipantStatus):
                latest.cvd_role = coerce_cvd_roles(roles)
        return data


class DeployerParticipant(CaseParticipant):
    """A CaseParticipant that holds the DEPLOYER role."""

    @model_validator(mode="before")
    @classmethod
    def _set_role(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        roles = [CVDRole.DEPLOYER]
        data["case_roles"] = roles
        ps_list = data.get("participant_statuses")
        if ps_list:
            latest = ps_list[-1]
            if isinstance(latest, ParticipantStatus):
                latest.cvd_role = coerce_cvd_roles(roles)
        return data


class CoordinatorParticipant(CaseParticipant):
    """A CaseParticipant that holds the COORDINATOR role."""

    @model_validator(mode="before")
    @classmethod
    def _set_role(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        roles = [CVDRole.COORDINATOR]
        data["case_roles"] = roles
        ps_list = data.get("participant_statuses")
        if ps_list:
            latest = ps_list[-1]
            if isinstance(latest, ParticipantStatus):
                latest.cvd_role = coerce_cvd_roles(roles)
        return data


class OtherParticipant(CaseParticipant):
    """A CaseParticipant that holds the OTHER role."""

    @model_validator(mode="before")
    @classmethod
    def _set_role(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        roles = [CVDRole.OTHER]
        data["case_roles"] = roles
        ps_list = data.get("participant_statuses")
        if ps_list:
            latest = ps_list[-1]
            if isinstance(latest, ParticipantStatus):
                latest.cvd_role = coerce_cvd_roles(roles)
        return data


class CaseActorParticipant(CaseParticipant):
    """A participant that acts as the CaseActor service for a VulnerabilityCase.

    Holds both ``COORDINATOR`` and ``CASE_MANAGER`` roles (CBT-01-003).
    The ``attributed_to`` field identifies the ActivityStreams Service URI
    that will send ``Announce(VulnerabilityCase)`` updates on behalf of the
    case owner.  Receivers use this participant to establish trusted CaseActor
    identity during bootstrap.
    """

    @model_validator(mode="before")
    @classmethod
    def _set_role(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        roles = [CVDRole.COORDINATOR, CVDRole.CASE_MANAGER]
        data["case_roles"] = roles
        ps_list = data.get("participant_statuses")
        if ps_list:
            latest = ps_list[-1]
            if isinstance(latest, ParticipantStatus):
                latest.cvd_role = coerce_cvd_roles(roles)
        return data


# ---------------------------------------------------------------------------
# Backward-compatibility alias
# ---------------------------------------------------------------------------

#: Alias kept for backward compatibility.  New code should import
#: :class:`CaseParticipant` directly.
VultronParticipant = CaseParticipant
