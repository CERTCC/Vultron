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

"""The CASE_MANAGER's repeat guard for a proposal of terms already held (#5720).

Each proposal mints a fresh ``EmbargoEvent`` id, so duplicate detection by id
(ID-02-001) never matches a repeat of the same terms.  EP-09-032 decides the
repeat by its effect instead: a proposal whose end time equals that of a
pending proposal in the case's register, or, with no revision pending, that of
the embargo in force, is a duplicate whoever sent it and whatever its ids.  It
changes no state, adds no ledger entry and relays no Invite, like a repeated
answer (CM-13-005).

During a revision the in-force end time is not a duplicate: it is a
counter-proposal to keep the current terms (EP-09-020), so it is committed.

Provides:

- :class:`EmbargoTermsNotHeldNode` — precondition guard that fails, with
  :attr:`~EmbargoTermsNotHeldNode.is_repeat` set, when the case already holds
  the proposed end time.

The guard runs only where the CASE_MANAGER registers a proposal
(EP-09-001): behind the CASE_MANAGER gate of
:func:`~vultron.core.behaviors.embargo.nodes.relay_guards.case_manager_admits_proposal_guard`
on the received side, where a relayed Invite names terms the CASE_MANAGER
already admitted, and in the CASE_MANAGER arm of its own propose and revise
triggers (``trigger_tree/proposal.py``).  A trigger admits only valid steps,
so there the repeat is a refusal of the whole request, not a no-op (#5899).
"""

from datetime import datetime

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.behaviors.idempotency import FlaggedRepeatGuardMixin
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.embargo_register import EmbargoRegisterEntry
from vultron.core.services.embargo_ordering import read_embargo_event
from vultron.core.states.embargo_register import EmbargoRegisterStatus
from vultron.errors import VultronError, VultronInvalidStateTransitionError


class EmbargoTermsNotHeldNode(
    FlaggedRepeatGuardMixin, DataLayerConditionWithPorts
):
    """Guard: the case does not already hold the proposed end time.

    FAILURE with :attr:`is_repeat` set when the proposal's end time equals
    that of a ``PROPOSED`` register entry, or, when no entry is ``PROPOSED``,
    that of the ``ACTIVE`` one (EP-09-032).  The handler reports the run as
    ``SKIPPED``: the commit would add an entry that changes nothing and the
    relay would ask every participant again about terms they already hold.

    SUCCESS when the end time is new, and when there is nothing to compare: the
    store holds no case, or the proposed terms do not resolve to a stored
    ``EmbargoEvent`` (``read_embargo_event`` raises a ``VultronError``).  A
    register entry that does not resolve is left out of the comparison with a
    WARNING.  Any other error propagates.  A duplicate
    is a no-op, never a refusal, so a guard that cannot prove one admits the
    proposal and the effect path decides what it means.

    Given *result_out*, as the CASE_MANAGER's own trigger tree gives it, a
    repeat also writes a ``VultronInvalidStateTransitionError`` to
    ``result_out["error"]``: the trigger refuses the whole request, which then
    registers, commits and relays nothing (RSH-09, #5899).  The received
    tree passes none and reports the repeat as ``SKIPPED``.

    Keyed on the terms alone, never on the sender, the activity id or the
    embargo id, which a repeat sent under new ids does not share.  The
    proposal's own register entry is left out: an Invite naming an embargo
    the register already holds repeats no other proposal's terms.  Read-only,
    so it runs in ``precondition_guards`` ahead of the guarded commit
    (CLP-10-006, CLP-10-009).
    """

    _REPEAT_FLAG = "is_repeat"

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        embargo: EmbargoEvent | None = None,
        result_out: dict[str, object] | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.embargo_id = embargo_id
        self.embargo = embargo
        self._result_out = result_out
        self.is_repeat = False
        """``True`` when the last run found the terms already held: a benign
        no-op, not a refusal."""

    def _proposed_end_time(self) -> datetime:
        """The proposal's end time: the inline terms, else the stored ones.

        Raises:
            VultronError: the stored terms do not resolve.
        """
        if self.embargo is not None:
            return self.embargo.end_time
        assert self.datalayer is not None
        return read_embargo_event(self.datalayer, self.embargo_id).end_time

    def _entry_end_time(self, entry: EmbargoRegisterEntry) -> datetime:
        """A register entry's end time.

        Raises:
            VultronError: the entry's terms do not resolve.
        """
        if isinstance(entry.embargo, EmbargoEvent):
            return entry.embargo.end_time
        assert self.datalayer is not None
        return read_embargo_event(self.datalayer, entry.embargo_id).end_time

    @staticmethod
    def _held_entries(
        case: VulnerabilityCase,
    ) -> list[EmbargoRegisterEntry]:
        """The entries whose terms a proposal would repeat (EP-09-032).

        The pending proposals; with none pending, the embargo in force.
        """
        pending = [
            e
            for e in case.embargo_register
            if e.status == EmbargoRegisterStatus.PROPOSED
        ]
        if pending:
            return pending
        return [
            e
            for e in case.embargo_register
            if e.status == EmbargoRegisterStatus.ACTIVE
        ]

    def update(self) -> Status:
        self.is_repeat = False
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        # The guards ahead of this one report a missing case (ADR-0087).
        case = self.datalayer.read(self.case_id)
        if not isinstance(case, VulnerabilityCase):
            return Status.SUCCESS
        try:
            end_time = self._proposed_end_time()
        except VultronError as exc:
            self.logger.debug(
                "%s: proposed terms '%s' not readable (%s) — nothing to"
                " compare",
                self.name,
                self.embargo_id,
                exc,
            )
            return Status.SUCCESS
        holding: EmbargoRegisterEntry | None = None
        for entry in self._held_entries(case):
            # The proposal's own entry is not a second proposal of its
            # terms: an Invite naming an embargo the register already holds
            # is judged by id, by the guards and effects that read the
            # register.
            if entry.embargo_id == self.embargo_id:
                continue
            try:
                entry_end_time = self._entry_end_time(entry)
            except VultronError as exc:
                self.logger.warning(
                    "%s: register entry '%s' on case '%s' is not readable"
                    " (%s); left out of the duplicate check (EP-09-032)",
                    self.name,
                    entry.embargo_id,
                    self.case_id,
                    exc,
                )
                continue
            if entry_end_time == end_time:
                holding = entry
                break
        if holding is None:
            return Status.SUCCESS
        self.is_repeat = True
        held_as = (
            "the embargo in force"
            if holding.status == EmbargoRegisterStatus.ACTIVE
            else "a pending proposal"
        )
        self.feedback_message = (
            f"Embargo '{self.embargo_id}' on case '{self.case_id}' ends at"
            f" {end_time.isoformat()}, as {held_as} '{holding.embargo_id}'"
            " does — repeat, nothing to apply (EP-09-032)"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        if self._result_out is not None:
            self._result_out["error"] = VultronInvalidStateTransitionError(
                f"Cannot propose embargo: {self.feedback_message}"
            )
        return Status.FAILURE


__all__ = [
    "EmbargoTermsNotHeldNode",
]
