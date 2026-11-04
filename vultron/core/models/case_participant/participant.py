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

"""Domain representation of a case participant (:class:`CaseParticipant`)."""

from __future__ import annotations

import logging
from typing import Any, Literal

from pydantic import (
    Field,
    ValidationInfo,
    field_serializer,
    field_validator,
    model_validator,
)

from vultron.core.models._helpers import new_object_id
from vultron.core.models.base import CoreObject, NonEmptyString
from vultron.core.models.case_participant._consent import (
    EmbargoConsentRowsMixin,
)
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.participant_status import (
    ParticipantStatus,
    coerce_cvd_roles,
    participant_status_rm_state,
)
from vultron.core.models.wire_keys import first_input, input_keys
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole, serialize_roles, validate_roles
from vultron.errors import (
    VultronValidationError,
)

logger = logging.getLogger(__name__)


class CaseParticipant(CoreObject, EmbargoConsentRowsMixin):
    """Domain representation of a case participant.

    Canonical core type that mirrors the Vultron-specific fields of the wire
    ``CaseParticipant`` class and all its role subclasses.

    ``type_`` is ``Literal["CaseParticipant"]`` so this class auto-registers
    in :data:`CORE_VOCABULARY` and round-trips through the DataLayer.

    Role-specific subclasses (:class:`ReporterParticipant`,
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
    # Consent is per (participant, embargo) (ADR-0122, CM-10-001, CM-18-001):
    # one row for every entry in the case's embargo register, and the only
    # record of consent.  Each invitation's RSVP deadline is on its row.
    # Bound-by-the-active-embargo and lapsed are lookups over these rows
    # (``is_signatory``, ``has_lapsed``), never stored.
    embargo_consents: list[EmbargoConsent] = Field(default_factory=list)
    # The participant has joined the case: it was seated by the case
    # initialization sequence (CM-14-001) or it accepted its stub Invite
    # (CM-10-004, ADR-0114).  One input to the case-level active check
    # (``VulnerabilityCase.is_active_participant``), never the answer itself.
    # Replicated with the record so every replica derives the same answer.
    # Defaults to True because a record seated by case initialization has
    # joined; the record the stub Invite creates (CM-11-006) sets False
    # explicitly, and the Accept of that Invite flips it to True.
    joined: bool = True
    # The removal fact (CM-31-001, ADR-0116): the id of the ``Remove`` activity
    # that took this participant out of active participation, or ``None`` when
    # it is not removed.  Removal keeps the record on the roster; this fact is
    # the second input to the case-level active check
    # (``VulnerabilityCase.is_active_participant``), never the answer itself.
    # The Case Owner's ``Remove(CaseParticipant)`` sets it (#4080) and
    # its ``Add(CaseParticipant)`` clears it (#4081).  Storing the activity id
    # rather than a flag keeps the fact replicable from the ledger entry
    # that records it, and names that entry for the reinstatement backfill
    # (CM-10-006).  ``NonEmptyString | None`` follows "if present, then
    # non-empty" (CS-08-002).
    removal_activity: NonEmptyString | None = None
    participant_case_name: NonEmptyString | None = None

    @field_validator("embargo_consents", mode="after")
    @classmethod
    def _rows_are_this_participants(
        cls, rows: list[EmbargoConsent], info: ValidationInfo
    ) -> list[EmbargoConsent]:
        """Attribute every row to this participant's actor (ADR-0122).

        A row is an AS2 object attributed to the actor whose consent it is,
        so a row the record seats without an actor takes the record's.  A
        row attributed to another actor is refused.  Runs on assignment too
        (``validate_assignment``), so every row write is covered.
        """
        actor_id = info.data.get("attributed_to")
        if actor_id is None:
            return rows
        return [row.for_actor(actor_id) for row in rows]

    @field_serializer("case_roles")
    def _serialize_case_roles(self, value: list[CVDRole]) -> list[str]:
        return serialize_roles(value)

    @field_validator("case_roles", mode="before")
    @classmethod
    def _validate_case_roles(cls, value: object) -> list[CVDRole]:
        return validate_roles(value, field_name="case_roles")

    @model_validator(mode="before")
    @classmethod
    def _set_name_if_empty(cls, data: Any) -> Any:
        """If ``name`` is unset, derive it from ``attributed_to``.

        Reads every input spelling (ARCH-25-002), so AS2 input derives the
        same name as its Python-named twin.
        """
        if not isinstance(data, dict):
            return data
        name = first_input(data, cls, "name")
        attributed_to = first_input(data, cls, "attributed_to")
        if name is None and attributed_to is not None:
            data = dict(data)
            data["name"] = attributed_to
        return data

    @model_validator(mode="before")
    @classmethod
    def _init_participant_status_if_empty(cls, data: Any) -> Any:
        """Seed ``participant_statuses`` with a default entry when absent.

        Reads every input spelling of each field it uses (ARCH-25-002,
        ADR-0099).  An AS2 dump carries the statuses under their alias; seeding
        beside them drew an id and read the clock for a status the alias then
        discarded (#5510).  AS2 input seeds the same status as its
        Python-named twin.
        """
        if not isinstance(data, dict):
            return data
        if any(key in data for key in input_keys(cls, "participant_statuses")):
            return data
        data = dict(data)
        id_val = first_input(data, cls, "id_")
        if not id_val:
            id_val = data["id"] = new_object_id()
        data["participant_statuses"] = [
            ParticipantStatus(
                context=first_input(data, cls, "context") or id_val,
                attributed_to=first_input(data, cls, "attributed_to"),
                cvd_role=coerce_cvd_roles(
                    first_input(data, cls, "case_roles") or []
                ),
            ),
        ]
        return data

    def _sync_latest_status_metadata(self) -> None:
        if not self.participant_statuses:
            return
        latest = self.participant_statuses[-1]
        latest.cvd_role = coerce_cvd_roles(self.case_roles)

    @property
    def removed(self) -> bool:
        """True when this participant carries the removal fact (CM-31-001).

        One input to the case-level active check, not a partial answer to
        it: a participant that is not removed may still be inert (it has not
        joined, or is not a signatory to the active embargo).  Use
        :meth:`VulnerabilityCase.is_active_participant` to decide
        entitlement (CM-31-002).
        """
        return self.removal_activity is not None

    def record_removal(self, removal_activity_id: str) -> bool:
        """Set the removal fact from the ``Remove`` activity that decided it.

        The one write of :attr:`removal_activity` for a removal (CM-31-001):
        the CASE_MANAGER calls it for the Case Owner's received
        ``Remove(CaseParticipant)``, and a replica calls it when it replays
        that activity's ledger entry (CM-31-007), so both record the same
        fact.  The record stays on the roster, and its status history and
        embargo consent rows are untouched (CM-31-008).  A participant that
        is already removed keeps its first removal: the call is a no-op and
        returns ``False``.  The caller persists the record.

        Returns:
            ``True`` when the fact was set, ``False`` when already removed.
        """
        if self.removed:
            return False
        self.removal_activity = removal_activity_id
        return True

    def clear_removal(self) -> bool:
        """Clear the removal fact: the participant is reinstated (CM-31-034).

        The one write that reverses :meth:`record_removal`.  The CASE_MANAGER
        calls it for the Case Owner's received ``Add(CaseParticipant)``, and a
        replica calls it when it replays that activity's ledger entry, so both
        hold the same record.  Nothing else changes: the participant does not
        accept again, and its status history and embargo consent rows stay as
        they were (ADR-0116).  A participant that is not removed is left as it
        is: the call is a no-op and returns ``False``.  The caller persists
        the record.

        Returns:
            ``True`` when the fact was cleared, ``False`` when not removed.
        """
        if not self.removed:
            return False
        self.removal_activity = None
        return True

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
        # A list, not a set: the roles are serialized in this order, and set
        # order follows PYTHONHASHSEED, so two runs would hash differently.
        # dict.fromkeys drops a duplicate the set used to drop, in held order.
        roles = list(dict.fromkeys(self.case_roles))
        if role not in roles:
            roles.append(role)
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
        self.case_roles = roles
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
        roles = list(dict.fromkeys(self.case_roles))  # as in add_role
        if role in roles:
            roles = [held for held in roles if held != role]
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
        self.case_roles = roles
        self._sync_latest_status_metadata()

    def has_role(self, role: CVDRole) -> bool:
        """Return ``True`` when the participant holds the given role."""
        return role in self.case_roles

    @property
    def roles(self) -> list[CVDRole]:
        """Return the participant's current CVD roles as a read-only copy."""
        return list(self.case_roles)
