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

``CaseParticipant`` is the canonical core type.

Several convenience subclasses are provided that auto-set ``case_roles`` via
model validators:

- :class:`FinderParticipant`
- :class:`ReporterParticipant`
- :class:`FinderReporterParticipant`
- :class:`VendorParticipant`
- :class:`DeployerParticipant`
- :class:`CoordinatorParticipant`
- :class:`ObserverParticipant`
- :class:`CaseActorParticipant`
"""

from __future__ import annotations

import logging
from collections.abc import Collection
from datetime import datetime
from typing import Any, ClassVar, Literal

from pydantic import Field, field_serializer, field_validator, model_validator

from vultron.core.models._helpers import _new_urn
from vultron.core.models.base import CoreObject, NonEmptyString
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.participant_status import (
    ParticipantStatus,
    coerce_cvd_roles,
    participant_status_rm_state,
)
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
    PEC_Trigger,
    consent_after,
    consent_trigger_is_legal,
)
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole, serialize_roles, validate_roles
from vultron.errors import VultronValidationError

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

    local_only_fields: ClassVar[frozenset[str]] = frozenset(
        {"invite_rsvp_deadline"}
    )

    type_: Literal["CaseParticipant"] = Field(
        default="CaseParticipant",
        validation_alias="type",
        serialization_alias="type",
    )
    case_roles: list[CVDRole] = Field(default_factory=list)
    participant_statuses: list[ParticipantStatus] = Field(default_factory=list)
    # Consent is per (participant, embargo) (ADR-0120, CM-10-001, CM-18-001):
    # one row for each embargo this participant was asked about, and the only
    # record of consent.  Bound-by-the-active-embargo and lapsed are lookups
    # over these rows (``is_signatory``, ``has_lapsed``), never stored.
    embargo_consents: list[EmbargoConsent] = Field(default_factory=list)
    # The participant has joined the case: it was seated by the case
    # initialization sequence (CM-14-001) or it accepted its stub Invite
    # (CM-10-004, ADR-0114).  One input to the case-level active check
    # (``VulnerabilityCase.is_active_participant``), never the answer itself.
    # Replicated with the record so every replica derives the same answer.
    # Defaults to True because every record created today is created at one of
    # those two moments — case initialization or the Accept of the Invite; the
    # record created at Invite time (#4048) sets False explicitly.
    joined: bool = True
    participant_case_name: NonEmptyString | None = None
    # Local bookkeeping, not an AS2 property: the deadline by which this actor's
    # own implementation wants an RSVP.  Kept in the stored row and dropped from
    # the delivery payload — see ``CoreObject.local_only_fields``, and note that
    # plain ``exclude=True`` would have stopped it being persisted at all.
    invite_rsvp_deadline: datetime | None = None

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
        if "participant_statuses" in data:
            return data
        data = dict(data)
        if not data.get("id") and not data.get("id_"):
            data["id"] = _new_urn()
        id_val = data.get("id") or data.get("id_")
        data["participant_statuses"] = [
            ParticipantStatus(
                context=data.get("context") or id_val,
                attributed_to=data.get("attributed_to"),
                cvd_role=coerce_cvd_roles(data.get("case_roles") or []),
            ),
        ]
        return data

    def _sync_latest_status_metadata(self) -> None:
        if not self.participant_statuses:
            return
        latest = self.participant_statuses[-1]
        latest.cvd_role = coerce_cvd_roles(self.case_roles)

    def consent_for(self, embargo_id: str) -> EmbargoConsentState | None:
        """This participant's consent to *embargo_id*; ``None`` when never asked."""
        for row in self.embargo_consents:
            if row.embargo_id == embargo_id:
                return row.state
        return None

    def accepts_pec_trigger(
        self, embargo_id: str, trigger: PEC_Trigger
    ) -> bool:
        """True when *trigger* is legal from the current row for *embargo_id*.

        The read-only twin of :meth:`apply_pec_transition`, for a caller that applies
        a trigger only where CM-18-003 allows it.  Asking first, rather than
        catching the refusal, keeps the write path fail-closed for every
        caller that does not opt into the no-op.
        """
        return consent_trigger_is_legal(self.consent_for(embargo_id), trigger)

    def apply_pec_transition(
        self, embargo_id: str, trigger: PEC_Trigger
    ) -> None:
        """Apply *trigger* to the consent row for *embargo_id*.

        The single authoritative consent-write path (CM-18-005, CM-18-006,
        ADR-0120): fail-closed against the transition table, creating the row
        on first contact.  Raises
        :exc:`~vultron.errors.VultronInvalidStateTransitionError` on an
        illegal trigger.  The caller persists the record.
        """
        new_state = consent_after(self.consent_for(embargo_id), trigger)
        self._set_consent(embargo_id, new_state)

    def apply_pec_transition_if_legal(
        self, embargo_id: str, trigger: PEC_Trigger
    ) -> bool:
        """Apply *trigger* when CM-18-003 allows it; True when the row moved.

        The one "apply where legal" shape for every caller that treats an
        illegal trigger as a recorded no-op rather than a fault.  The caller
        persists the record.
        """
        if not self.accepts_pec_trigger(embargo_id, trigger):
            return False
        self.apply_pec_transition(embargo_id, trigger)
        return True

    def _set_consent(
        self, embargo_id: str, state: EmbargoConsentState
    ) -> None:
        rows = [r for r in self.embargo_consents if r.embargo_id != embargo_id]
        self.embargo_consents = [
            *rows,
            EmbargoConsent(embargo_id=embargo_id, state=state),
        ]

    def invited_embargo_ids(self) -> list[str]:
        """Ids of the embargoes this participant was invited to and has not answered."""
        return [
            r.embargo_id
            for r in self.embargo_consents
            if r.state == EmbargoConsentState.INVITED
        ]

    def is_signatory(self, active_embargo_id: str | None) -> bool:
        """True when this participant has accepted the embargo in force.

        "Signatory" is a lookup, not a state: the row for the active embargo
        says ``ACCEPTED`` (CM-18-001).  With no embargo in force nobody is a
        signatory.
        """
        return (
            active_embargo_id is not None
            and self.consent_for(active_embargo_id)
            == EmbargoConsentState.ACCEPTED
        )

    def has_lapsed(
        self,
        active_embargo_id: str | None,
        open_proposal_ids: Collection[str] = (),
    ) -> bool:
        """True when it accepted an earlier embargo but not the one in force.

        Derived (CM-18-001): the participant holds an ``ACCEPTED`` row for
        some other embargo and has no accepting row for the active one.  An
        ``ACCEPTED`` row for one of *open_proposal_ids* does not count: the
        participant accepted a revision it was never bound by, so it has
        nothing to lapse from.  A ``DECLINED`` row for the active embargo is a
        refusal, not a lapse; a participant that was never bound by anything
        has not lapsed either.
        """
        if active_embargo_id is None:
            return False
        if self.consent_for(active_embargo_id) in (
            EmbargoConsentState.ACCEPTED,
            EmbargoConsentState.DECLINED,
        ):
            return False
        return any(
            r.state == EmbargoConsentState.ACCEPTED
            and r.embargo_id not in open_proposal_ids
            for r in self.embargo_consents
        )

    def sign_embargo(self, embargo_id: str) -> bool:
        """Sign *embargo_id*, the embargo in force; True when now ACCEPTED.

        The one seeding shape for a participant that consents to the active
        embargo without an answer of its own (CM-14-005, CM-10-001): apply
        ``ACCEPT`` where CM-18-003 allows it.  A participant that declined
        this embargo is left as it is, so the content gate (CM-10-004) never
        admits an actor whose row says it is not bound.  The caller persists
        the record.
        """
        self.apply_pec_transition_if_legal(embargo_id, PEC_Trigger.ACCEPT)
        return self.consent_for(embargo_id) == EmbargoConsentState.ACCEPTED

    @property
    def rm_closed(self) -> bool:
        """True when any recorded RM state is ``CLOSED``.

        ``CLOSED`` is terminal (ADR-0085), so any status recording it means the
        participant has closed, whatever the order of the history.
        """
        return any(
            participant_status_rm_state(status) == RM.CLOSED
            for status in self.participant_statuses
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
                # S608 false positive: "delete from" is prose, not SQL.
                raise KeyError(
                    f"Role {role} was not present to delete from participant.case_roles"  # noqa: S608
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


def _seed_accepted_status(data: Any) -> Any:
    """Seed ``participant_statuses`` with a single ``RM.ACCEPTED`` rung.

    A reporter has, by definition, accepted the report, so its first ladder
    rung is ``RM.ACCEPTED``.  Shared by :class:`ReporterParticipant` and
    :class:`FinderReporterParticipant`, which previously carried byte-identical
    copies (de-duplicated per ADR-0089 AC-5, ARCH-15-004, CS-22-001).
    """
    if not isinstance(data, dict):
        return data
    data = dict(data)
    if not data.get("id") and not data.get("id_"):
        data["id"] = _new_urn()
    id_val = data.get("id") or data.get("id_")
    data["participant_statuses"] = [
        ParticipantStatus(
            context=data.get("context") or id_val,
            attributed_to=data.get("attributed_to"),
            rm=RmDimension(state=RM.ACCEPTED),
            cvd_role=coerce_cvd_roles(data.get("case_roles") or []),
        )
    ]
    return data


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
        return _seed_accepted_status(data)


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
        return _seed_accepted_status(data)


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


class ObserverParticipant(CaseParticipant):
    """A CaseParticipant that holds the OBSERVER role (ADR-0057)."""

    @model_validator(mode="before")
    @classmethod
    def _set_role(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        roles = [CVDRole.OBSERVER]
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
