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

"""The embargo register views and writer of a :class:`VulnerabilityCase`.

The register is append-only and the case's EM, active embargo and open
proposals are all read from it (ADR-0122).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vultron.core.models._helpers import (
    _as_id,
)
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.embargo_register import (
    EmbargoRegisterEntry,
    RegisterChange,
    apply_register_step,
)
from vultron.core.models.embargo_termination import EmbargoTermination
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import (
    EmbargoRegisterStatus,
    derive_em,
)
from vultron.errors import VultronNotFoundError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from vultron.core.models.base import NonEmptyString


class EmbargoRegisterMixin:
    """Embargo-register methods of :class:`VulnerabilityCase` (ADR-0122)."""

    if TYPE_CHECKING:
        # The model's fields this mixin reads and writes.
        id_: NonEmptyString
        case_participants: list[NonEmptyString | CaseParticipant]
        case_statuses: list[NonEmptyString | CaseStatus]
        embargo_register: list[EmbargoRegisterEntry]
        pending_embargo_proposal_index: dict[NonEmptyString, NonEmptyString]

        def _last_materialized_status(self) -> CaseStatus | None: ...

    def apply_embargo_register_step(
        self,
        changes: list[RegisterChange],
        *,
        threat_signal: bool = False,
    ) -> None:
        """Apply one register step, the only writer of the case's embargoes.

        The step is checked whole by
        :func:`~vultron.core.models.embargo_register.apply_register_step`
        and refused, leaving the case untouched, when any rule breaks.  An
        entry that has left ``PROPOSED`` takes its relay record out of
        ``pending_embargo_proposal_index`` with it (EP-08-003); a record for
        an embargo the register has not recorded yet stays (EP-09-007).  The
        current :class:`CaseStatus` is stamped with the derived EM, so the
        copy it carries on the wire never disagrees with the register.

        Raises:
            VultronInvalidStateTransitionError: the step breaks a register
                rule or invariant.
        """
        register = apply_register_step(
            self.embargo_register, changes, threat_signal=threat_signal
        )
        # A participant held inline must already hold the new entries' rows
        # when the register is assigned, or the row check refuses the
        # assignment (validate_assignment).  Stored participants get theirs
        # from the lifecycle service, which persists them (ADR-0122).
        embargo_ids = [entry.embargo_id for entry in register]
        for participant in self.case_participants:
            if isinstance(participant, CaseParticipant):
                participant.write_uninvited_rows(embargo_ids)
        self.embargo_register = register
        undecided = self.undecided_proposals(
            self.pending_embargo_proposal_index
        )
        if undecided != self.pending_embargo_proposal_index:
            self.pending_embargo_proposal_index = undecided
        self._stamp_em()

    def undecided_proposals(self, index: Mapping[str, str]) -> dict[str, str]:
        """The entries of *index* whose embargo is still undecided here.

        The one filter every writer of ``pending_embargo_proposal_index``
        applies, so the record never holds a decided proposal whichever
        order a register step, a relayed Invite or a case copy arrives in
        (EP-08-003, SYNC-19-001).
        """
        return {
            embargo_id: invite_id
            for embargo_id, invite_id in index.items()
            if self.proposal_is_undecided(embargo_id)
        }

    def proposal_is_undecided(self, embargo_id: str) -> bool:
        """Whether *embargo_id* may still be answered as a proposal.

        True for a ``PROPOSED`` entry, and for an embargo the register has
        not recorded yet: a replica indexes a relayed Invite when it arrives,
        which can be before ledger replay records the proposal (EP-09-007).
        False once the entry has left ``PROPOSED`` (EP-08-003), and for every
        embargo once one has terminated: nothing is proposed after that
        (EP-08-004, register invariant 4).
        """
        entry = self.embargo_register_entry(embargo_id)
        if entry is None:
            return not any(
                e.status == EmbargoRegisterStatus.TERMINATED
                for e in self.embargo_register
            )
        return entry.status == EmbargoRegisterStatus.PROPOSED

    def _em_stamped_statuses(
        self,
    ) -> list[str | CaseStatus] | None:
        """``case_statuses`` with the current status's EM copy set from the register.

        ``None`` when there is no materialized status or its copy already
        agrees.  The status is replaced by a copy, never mutated, so a status
        object a caller handed in is left as it was.
        """
        current = self._last_materialized_status()
        if current is None:
            return None
        em = self.em_state
        if current.em.state == em:
            return None
        stamped = current.with_em(em)
        return [stamped if s is current else s for s in self.case_statuses]

    def _stamp_em(self) -> None:
        """Write the derived EM onto the current status's copy (ADR-0122).

        Bypasses assignment validation like :meth:`_set_cs_context`: the copy
        differs only by a freshly validated ``EmDimension`` and the label
        :meth:`CaseStatus.with_em` derives from it (ARCH-21-004).
        """
        statuses = self._em_stamped_statuses()
        if statuses is not None:
            object.__setattr__(self, "case_statuses", statuses)

    @property
    def register_embargo_ids(self) -> list[str]:
        """The embargo id of every register entry, in register order."""
        return [entry.embargo_id for entry in self.embargo_register]

    def embargo_register_entry(
        self, embargo_id: str
    ) -> EmbargoRegisterEntry | None:
        """The register entry for *embargo_id*, or ``None`` when it has none."""
        return next(
            (e for e in self.embargo_register if e.embargo_id == embargo_id),
            None,
        )

    def embargo_register_status(
        self, embargo_id: str
    ) -> EmbargoRegisterStatus:
        """The register status of *embargo_id*, the input every consent write needs.

        Raises:
            VultronNotFoundError: the register has no entry for *embargo_id*;
                a consent row exists only for a register entry (ADR-0122).
        """
        entry = self.embargo_register_entry(embargo_id)
        if entry is None:
            raise VultronNotFoundError(
                "EmbargoRegisterEntry", f"{embargo_id} on case {self.id_}"
            )
        return entry.status

    @property
    def em_state(self) -> EM:
        """The case's EM state, derived from its embargo register (ADR-0122)."""
        return derive_em(entry.status for entry in self.embargo_register)

    def em_state_without_proposal(self, embargo_id: str) -> EM:
        """The EM state derived with *embargo_id*'s open proposal set aside.

        A proposal's own ``PROPOSE`` entry is not "another embargo": a
        decision about that proposal reads the case as it stands apart from
        it, so it is the same whether the entry has reached this replica
        yet or not (SYNC-19-001).  Only a ``PROPOSED`` entry is set aside; a
        decided one counts like any other.  Dropping a ``PROPOSED`` entry
        leaves a legal register, whereas dropping an ``ACTIVE`` or
        ``TERMINATED`` one beside a ``SUPERSEDED`` entry would not (ADR-0122).
        """
        return derive_em(
            entry.status
            for entry in self.embargo_register
            if not (
                entry.embargo_id == embargo_id
                and entry.status == EmbargoRegisterStatus.PROPOSED
            )
        )

    @property
    def active_embargo(self) -> str | EmbargoEvent | None:
        """The embargo in force — the object when one was carried, else its id.

        A view of the register's ``ACTIVE`` entry.  Most callers want the id
        and should use :attr:`active_embargo_id`.
        """
        return next(
            (
                entry.embargo
                for entry in self.embargo_register
                if entry.status == EmbargoRegisterStatus.ACTIVE
            ),
            None,
        )

    @property
    def active_embargo_id(self) -> str | None:
        """The id of the register's ``ACTIVE`` entry, or ``None``."""
        return _as_id(self.active_embargo)

    @property
    def embargo_termination(
        self,
    ) -> EmbargoTermination | None:
        """How the case's embargo ended, or ``None`` while none has (ADR-0122).

        The ``termination`` of the register's ``TERMINATED`` entry.
        """
        return next(
            (
                entry.termination
                for entry in self.embargo_register
                if entry.status == EmbargoRegisterStatus.TERMINATED
            ),
            None,
        )

    @property
    def proposed_embargo_ids(self) -> list[str]:
        """The ids of the open proposals: the register's ``PROPOSED`` entries."""
        return [
            entry.embargo_id
            for entry in self.embargo_register
            if entry.status == EmbargoRegisterStatus.PROPOSED
        ]

    @property
    def embargo_in_force(self) -> bool:
        """True when this case's register has an ``ACTIVE`` entry.

        Read from :attr:`active_embargo_id`, the same fact the consent
        bookkeeping keys on (``embargo_lifecycle.pec``): an entry is
        ``ACTIVE`` from its activation until a revision supersedes it or the
        embargo is terminated, so it holds through a revision (EM
        ``REVISE``).  A proposal alone does not make one.
        """
        return self.active_embargo_id is not None
