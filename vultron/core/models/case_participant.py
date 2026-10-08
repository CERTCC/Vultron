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
from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_serializer, field_validator, model_validator

from vultron.core.models._helpers import _new_urn
from vultron.core.models.base import CoreObject, NonEmptyString
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.embargo_register import EmbargoRegisterEntry
from vultron.core.models.participant_status import (
    ParticipantStatus,
    coerce_cvd_roles,
    participant_status_rm_state,
)
from vultron.core.states.embargo_register import (
    FINAL_REGISTER_STATUSES,
    EmbargoRegisterStatus,
)
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
    PEC_Trigger,
    consent_after,
    consent_trigger_is_legal,
)
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole, serialize_roles, validate_roles
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronNotFoundError,
    VultronValidationError,
)

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
    # Defaults to True because every record created today is created at one of
    # those two moments — case initialization or the Accept of the Invite; the
    # record created at Invite time (#4048) sets False explicitly.
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

    def _row(self, embargo_id: str) -> EmbargoConsent:
        """The consent row for *embargo_id*.

        Raises:
            VultronNotFoundError: the participant holds no row for it.  Every
                register entry has a row on every participant (ADR-0122), so
                a missing one is a defect, never "not asked".
        """
        for row in self.embargo_consents:
            if row.embargo_id == embargo_id:
                return row
        raise VultronNotFoundError(
            "EmbargoConsent", f"{embargo_id} on participant {self.id_}"
        )

    def consent_for(self, embargo_id: str) -> EmbargoConsentState:
        """This participant's consent to *embargo_id*; raises when it has no row."""
        return self._row(embargo_id).state

    def rsvp_deadline_for(self, embargo_id: str) -> datetime | None:
        """The RSVP deadline of the invitation the row for *embargo_id* awaits."""
        return self._row(embargo_id).rsvp_deadline

    def write_uninvited_rows(self, embargo_ids: Iterable[str]) -> bool:
        """Write an ``UNINVITED`` row for each of *embargo_ids* it has none for.

        The creation write of the consent table (ADR-0122): a participant
        gets a row when an embargo is proposed and, when it joins, one for
        every entry already in the register.  A row it already holds is left
        as it is, so the call is idempotent.  It records no answer, so it is
        not a consent change (CM-18-005).  The caller persists the record.

        Returns:
            ``True`` when at least one row was written.
        """
        held = {row.embargo_id for row in self.embargo_consents}
        new_ids = [i for i in dict.fromkeys(embargo_ids) if i not in held]
        if not new_ids:
            return False
        self.embargo_consents = [
            *self.embargo_consents,
            *(
                EmbargoConsent(
                    embargo_id=i, state=EmbargoConsentState.UNINVITED
                )
                for i in new_ids
            ),
        ]
        return True

    def accepts_pec_trigger(
        self,
        embargo_id: str,
        trigger: PEC_Trigger,
        *,
        entry_status: EmbargoRegisterStatus,
    ) -> bool:
        """True when *trigger* would move the row for *embargo_id*.

        The read-only twin of :meth:`apply_pec_transition`, for a caller that
        applies a trigger only where it is legal.  Asking first, rather than
        catching the refusal, keeps the write path fail-closed for every
        caller that does not opt into the no-op.  *entry_status* is the
        register status of the embargo's entry: a row for a final entry
        accepts no trigger (ADR-0122).
        """
        return entry_status not in FINAL_REGISTER_STATUSES and (
            consent_trigger_is_legal(self.consent_for(embargo_id), trigger)
        )

    def apply_pec_transition(
        self,
        embargo_id: str,
        trigger: PEC_Trigger,
        *,
        entry_status: EmbargoRegisterStatus,
        rsvp_deadline: datetime | None = None,
    ) -> None:
        """Apply *trigger* to the consent row for *embargo_id*.

        The single authoritative consent-write path (CM-18-005, CM-18-006,
        ADR-0122): fail-closed against the transition table and against the
        register.  *entry_status* is the register status of the embargo's
        entry; a row for a final entry (``SUPERSEDED``, ``REJECTED``,
        ``CANCELLED``, ``TERMINATED``) is frozen.  *rsvp_deadline* is the
        invitation's deadline and is accepted only with ``INVITE``; any
        trigger that takes the row out of ``INVITED`` drops the deadline
        (CM-28-013).  The caller persists the record.

        Raises:
            VultronNotFoundError: the participant has no row for *embargo_id*.
            VultronInvalidStateTransitionError: the trigger is illegal from
                the row's state, or the entry is final.
            VultronValidationError: a deadline is given with a trigger other
                than ``INVITE``.
        """
        current = self.consent_for(embargo_id)
        if entry_status in FINAL_REGISTER_STATUSES:
            raise VultronInvalidStateTransitionError(
                f"PEC: embargo '{embargo_id}' is {entry_status}, so"
                f" participant {self.id_}'s consent row for it accepts no"
                f" trigger ('{trigger}' refused)."
            )
        if rsvp_deadline is not None and trigger != PEC_Trigger.INVITE:
            raise VultronValidationError(
                f"PEC: an RSVP deadline belongs to an invitation; trigger"
                f" '{trigger}' cannot carry one (CM-28-013)."
            )
        self._replace_row(
            EmbargoConsent(
                embargo_id=embargo_id,
                state=consent_after(current, trigger),
                rsvp_deadline=rsvp_deadline,
            )
        )

    def apply_pec_transition_if_legal(
        self,
        embargo_id: str,
        trigger: PEC_Trigger,
        *,
        entry_status: EmbargoRegisterStatus,
        rsvp_deadline: datetime | None = None,
    ) -> bool:
        """Apply *trigger* where it is legal; True when the row moved.

        The one "apply where legal" shape for every caller that treats an
        illegal trigger, or a frozen row, as a recorded no-op rather than a
        fault.  The caller persists the record.
        """
        if not self.accepts_pec_trigger(
            embargo_id, trigger, entry_status=entry_status
        ):
            return False
        self.apply_pec_transition(
            embargo_id,
            trigger,
            entry_status=entry_status,
            rsvp_deadline=rsvp_deadline,
        )
        return True

    def restamp_rsvp_deadline(
        self,
        embargo_id: str,
        rsvp_deadline: datetime | None,
        *,
        entry_status: EmbargoRegisterStatus,
    ) -> bool:
        """Give a still-``INVITED`` row the deadline of a fresh invitation.

        An Invite sent again to a participant that has not answered moves no
        state, but its deadline is now the one the row waits on (CM-28-013).
        A row that is not ``INVITED``, or whose entry is final, is left as
        it is.  The caller persists the record.

        Returns:
            ``True`` when the row's deadline changed.
        """
        row = self._row(embargo_id)
        if (
            entry_status in FINAL_REGISTER_STATUSES
            or row.state != EmbargoConsentState.INVITED
            or row.rsvp_deadline == rsvp_deadline
        ):
            return False
        self._replace_row(
            EmbargoConsent(
                embargo_id=embargo_id,
                state=row.state,
                rsvp_deadline=rsvp_deadline,
            )
        )
        return True

    def _replace_row(self, row: EmbargoConsent) -> None:
        """Swap in *row* for the row of the same embargo, keeping row order."""
        self.embargo_consents = [
            row if r.embargo_id == row.embargo_id else r
            for r in self.embargo_consents
        ]

    def is_signatory(self, active_embargo_id: str | None) -> bool:
        """True when this participant has agreed to the embargo in force.

        "Signatory" is a lookup, not a state: the row for the register's
        ``ACTIVE`` entry says ``AGREED`` (CM-18-001).  With no embargo in
        force nobody is a signatory.
        """
        return (
            active_embargo_id is not None
            and self.consent_for(active_embargo_id)
            == EmbargoConsentState.AGREED
        )

    def has_lapsed(self, register: Sequence[EmbargoRegisterEntry]) -> bool:
        """True when it was bound, and the embargo in force is one it did not agree to.

        Derived from the rows and *register*, the case's embargo register
        (ADR-0122, CM-18-001): an entry is ``ACTIVE``, this participant's row
        for it is neither ``AGREED`` nor ``DECLINED``, and, following
        ``replaces`` back from the ``ACTIVE`` entry, the first entry whose
        row is ``AGREED`` or ``DECLINED`` has an ``AGREED`` row.  Only the
        embargoes that were once in force are on that chain, so agreeing to a
        proposal that never took effect binds nothing to lapse from; and a
        participant that withdrew from a later embargo (a ``DECLINED`` row
        on the chain) has not lapsed when a further revision replaces it.
        With no ``ACTIVE`` entry nobody has lapsed.

        Raises:
            VultronValidationError: an entry on the chain names a ``replaces``
                the register does not hold.
            VultronNotFoundError: the participant has no row for an entry on
                the chain.
        """
        by_id = {entry.embargo_id: entry for entry in register}
        active = next(
            (e for e in register if e.status == EmbargoRegisterStatus.ACTIVE),
            None,
        )
        answered = (EmbargoConsentState.AGREED, EmbargoConsentState.DECLINED)
        if active is None or self.consent_for(active.embargo_id) in answered:
            return False
        replaced_id = active.replaces
        while replaced_id is not None:
            if replaced_id not in by_id:
                raise VultronValidationError(
                    f"Embargo register names '{replaced_id}' as replaced but"
                    " holds no entry for it; lapsed cannot be read."
                )
            state = self.consent_for(replaced_id)
            if state in answered:
                return state == EmbargoConsentState.AGREED
            replaced_id = by_id[replaced_id].replaces
        return False

    def sign_embargo(self, active_embargo_id: str) -> bool:
        """Agree to *active_embargo_id*, the embargo in force; True when now AGREED.

        The one seeding shape for a participant that consents to the active
        embargo without an answer of its own (CM-14-003, CM-14-005, the
        Accept of the full-case Invite): apply ``AGREE`` where it is legal.
        A participant that declined this embargo is left as it is, so the
        content gate (CM-10-004) never admits an actor whose row says it is
        not bound.  The caller passes the register's ``ACTIVE`` entry and
        persists the record.
        """
        self.apply_pec_transition_if_legal(
            active_embargo_id,
            PEC_Trigger.AGREE,
            entry_status=EmbargoRegisterStatus.ACTIVE,
        )
        return self.is_signatory(active_embargo_id)

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
