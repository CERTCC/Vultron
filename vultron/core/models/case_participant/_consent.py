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

"""The per-embargo consent rows of a :class:`CaseParticipant` (ADR-0122).

Consent is one row per (participant, register entry), the only record of
consent; signatory and lapsed are reads of the rows (CM-18-001, CM-18-016).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import TYPE_CHECKING

from vultron.core.models.base import NonEmptyString
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.embargo_register import EmbargoRegisterEntry
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
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronNotFoundError,
    VultronValidationError,
)


class EmbargoConsentRowsMixin:
    """Consent-row methods of :class:`CaseParticipant` (ADR-0122)."""

    if TYPE_CHECKING:
        # The model's fields this mixin reads and writes.
        id_: NonEmptyString
        embargo_consents: list[EmbargoConsent]

    def _row(self, embargo_id: str) -> EmbargoConsent:
        """The consent row for *embargo_id*.

        Raises:
            VultronNotFoundError: the participant holds no row for it.  Every
                register entry has a row on every participant (ADR-0122), so
                a missing one is a defect, never "not asked".
        """
        row = self.held_row(embargo_id)
        if row is not None:
            return row
        raise VultronNotFoundError(
            "EmbargoConsent", f"{embargo_id} on participant {self.id_}"
        )

    def held_row(self, embargo_id: str) -> EmbargoConsent | None:
        """The row for *embargo_id*, or ``None`` when the record holds none.

        For the apply function's starting-state check, where "no row yet" is
        what a ``Create`` entry expects.  Every other reader uses
        :meth:`consent_for`, which raises on a missing row.
        """
        return next(
            (r for r in self.embargo_consents if r.embargo_id == embargo_id),
            None,
        )

    def consent_for(self, embargo_id: str) -> EmbargoConsentState:
        """This participant's consent to *embargo_id*; raises when it has no row."""
        return self._row(embargo_id).state

    def rsvp_deadline_for(self, embargo_id: str) -> datetime | None:
        """The RSVP deadline of the invitation the row for *embargo_id* awaits."""
        return self._row(embargo_id).rsvp_deadline

    def missing_rows(self, embargo_ids: Iterable[str]) -> list[str]:
        """The ids among *embargo_ids* this participant holds no row for.

        In first-seen order, without repeats.
        """
        held = {row.embargo_id for row in self.embargo_consents}
        return [i for i in dict.fromkeys(embargo_ids) if i not in held]

    def write_uninvited_rows(self, embargo_ids: Iterable[str]) -> bool:
        """Write an ``UNINVITED`` row for each of *embargo_ids* it has none for.

        The creation write of the consent table (ADR-0122): a participant
        gets a row when an embargo is proposed (CM-18-019) and, when it
        joins, one for every entry already in the register (CM-18-020).  A
        row it already holds is left as it is, so the call is idempotent.  It
        records no answer, so it is not a consent change (CM-18-005).  The
        caller persists the record.

        Returns:
            ``True`` when at least one row was written.
        """
        new_ids = self.missing_rows(embargo_ids)
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

    def copy_consent_row(self, row: EmbargoConsent) -> None:
        """Write *row* as a ledger entry carries it: replace or append it.

        The write of the one apply function
        (:func:`~vultron.core.models.embargo_apply.apply_embargo_change`),
        which has already checked the starting state.  It runs no transition
        and stamps nothing (CM-23-016): the row is stored as carried, in place
        of the row for the same embargo, or after the others when it is new.
        The caller persists the record.
        """
        if self.held_row(row.embargo_id) is not None:
            self._replace_row(row)
        else:
            self.embargo_consents = [*self.embargo_consents, row]

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
                the register does not hold, or the chain loops.
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
        seen = {active.embargo_id}
        replaced_id = active.replaces
        while replaced_id is not None:
            if replaced_id not in by_id:
                raise VultronValidationError(
                    f"Embargo register names '{replaced_id}' as replaced but"
                    " holds no entry for it; lapsed cannot be read."
                )
            if replaced_id in seen:
                raise VultronValidationError(
                    f"Embargo register's replaces chain comes back to"
                    f" '{replaced_id}'; lapsed cannot be read."
                )
            seen.add(replaced_id)
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
        A participant that declined this embargo is left as it is: seeding is
        not an answer the participant gave, so it never overrides one it did
        give, and the content gate (CM-10-004) never admits an actor whose row
        says it is not bound.  Only the participant's own Accept of the
        embargo changes a decline (CM-18-003).  The caller passes the
        register's ``ACTIVE`` entry and persists the record.
        """
        if (
            self.consent_for(active_embargo_id)
            is not EmbargoConsentState.DECLINED
        ):
            self.apply_pec_transition_if_legal(
                active_embargo_id,
                PEC_Trigger.AGREE,
                entry_status=EmbargoRegisterStatus.ACTIVE,
            )
        return self.is_signatory(active_embargo_id)
