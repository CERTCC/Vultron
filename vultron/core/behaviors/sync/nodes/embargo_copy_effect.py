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

"""Replica slots that copy embargo entries through the one apply function.

Every replica writes the embargo register and the consent rows by copying the
CASE_MANAGER's entries through
:func:`~vultron.core.models.embargo_apply.apply_embargo_change`, the function
the CASE_MANAGER's own trial apply and apply use (ADR-0124, CM-23-016,
EMB-18-006).  :class:`ApplyEmbargoChangeFromLedgerNode` is the shared frame:
a subclass names the change its entry carries (:meth:`_change`), and the
frame reads the case file, applies the change, and saves what changed.

An entry whose starting state does not match this replica's case is refused,
never patched over: the frame holds the received ``Announce`` that carried
it, keyed on its predecessor hash (``hold_ledger_announce``, SYNC-14-001),
sends the CASE_MANAGER a ``LedgerEntryRefused/CaseDiverged`` fault
(SYNC-16-001), and fails, so the entry is not persisted (SYNC-12-001), and the
receive path reports it deferred.  The entry extends the stored chain, so the drain that
follows every received announce for the case replays that ``Announce`` and
retries it; it stays held until this replica's case reaches the entry's
start.  An entry this replica
had already applied, but not stored, is in place and passes as a no-op
(:func:`~vultron.core.models.embargo_apply.change_is_in_place`), and so does
an entry a refused apply shows the case is already past: a replica seeded
after the entry replays the ledger from genesis over that seed, and replay
moves forward only (CM-23-016, ADR-0114;
:func:`~vultron.core.models.embargo_apply.case_file_is_past`).

:class:`ApplyEmbargoConsentFromLedgerNode` is the first slot: the
CASE_MANAGER's ``Create(EmbargoConsent)`` and ``Update(EmbargoConsent)``
entries, each carrying one consent row in full.  The register-step slots of
the embargo acts subclass the same frame: the proposal's ``PROPOSE``
(``relay_effect.py``), the abandonment's ``CANCEL`` (``abandon.py``), the
teardown's ``TERMINATE`` (``teardown.py``), and the owner's ``ACTIVATE`` and
``REJECT`` (``activation_effect.py``).  A withdrawal's
``Leave`` carries no row, so its slot (``withdrawal.py``) copies nothing
itself: each row it declines is a consent entry this module's slot copies
(#4717).
"""

from __future__ import annotations

from py_trees.common import Status

from vultron.core.behaviors.embargo_case_file import (
    read_embargo_case_file,
    save_case_file,
)
from vultron.core.behaviors.sync.nodes._helpers import (
    _LedgerEffectNode,
    hold_received_announce,
)
from vultron.core.behaviors.sync.nodes.event_conditions import (
    _SemanticTypeSetNode,
)
from vultron.core.behaviors.sync.nodes.ledger_entry_fault import (
    emit_ledger_entry_fault,
)
from vultron.core.models._helpers import project_wire_snapshot_to_core
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.embargo_apply import (
    ConsentRowChange,
    EmbargoCaseFile,
    EmbargoChange,
    apply_embargo_change,
    case_file_is_past,
    change_is_in_place,
)
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.embargo_consent_semantic_types import (
    CONSENT_ROW_VERBS,
)
from vultron.core.models.fault_classes import (
    VULTRON_FAILURE_LEDGER_ENTRY_REFUSED_CASE_DIVERGED,
)
from vultron.errors import VultronEntryRefusedError


class ApplyEmbargoChangeFromLedgerNode(_LedgerEffectNode):
    """Copy one embargo entry onto this replica's case file, or refuse it.

    Subclasses implement :meth:`_change`.  SUCCESS when the change is applied
    and saved, when it is already in place (a re-applied entry), or when this
    replica holds no copy of the case (Regime 2, ADR-0087).  FAILURE when the entry is malformed, or when the apply
    function refuses it; the refused entry's ``Announce`` is held,
    :attr:`refused_into_gap` is set, and the CASE_MANAGER is sent the
    divergence fault (SYNC-16-001).
    """

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        #: True after a run whose entry the apply function refused.
        self.refused_into_gap = False

    def initialise(self) -> None:
        super().initialise()
        self.refused_into_gap = False

    def _change(self, entry: CaseLedgerEntry) -> EmbargoChange:
        """The change *entry* carries.

        Raises:
            TypeError: the snapshot carries no object of the expected shape.
            ValueError: the carried object is not a valid change.
        """
        raise NotImplementedError

    def _stated_changes(
        self, entry: CaseLedgerEntry, after: EmbargoCaseFile
    ) -> list[EmbargoChange]:
        """Further changes the entry's activity states, applied after it.

        *after* is the case file as :meth:`_change` leaves it.  An act's own
        activity can state more than one change (CLP-07-013): the owner's
        ``Accept(EmbargoEvent, target=Case)`` is the ``ACTIVATE`` step and
        the owner's agreement.  None by default.
        """
        return []

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        entry = self._get_entry()
        if self._resolve_case_replica(entry.case_id) is None:
            return Status.SUCCESS  # Regime 2 (ADR-0087): partial replica
        try:
            change = self._change(entry)
        except (TypeError, ValueError) as exc:
            self.feedback_message = (
                f"{self.name}: '{entry.semantic_type}' entry '{entry.id_}' does"
                f" not carry a valid change: {exc}"
            )
            self.logger.exception("%s", self.feedback_message)
            return Status.FAILURE

        before = read_embargo_case_file(self.datalayer, entry.case_id)
        if change_is_in_place(before, change):
            self.logger.debug(
                "%s: '%s' entry '%s' is already in place on case '%s' —"
                " idempotent no-op",
                self.name,
                entry.semantic_type,
                entry.id_,
                entry.case_id,
            )
            return Status.SUCCESS
        try:
            after = apply_embargo_change(before, change)
            for stated in self._stated_changes(entry, after):
                after = apply_embargo_change(after, stated)
        except VultronEntryRefusedError as exc:
            if case_file_is_past(before, change):
                # A seed taken after this entry: replay moves forward only
                # (CM-23-016, ADR-0114).
                self.logger.info(
                    "%s: case '%s' is already past '%s' entry '%s' (a seed"
                    " taken after it) — idempotent no-op",
                    self.name,
                    entry.case_id,
                    entry.semantic_type,
                    entry.id_,
                )
                return Status.SUCCESS
            return self._refuse(entry, exc)
        save_case_file(self.datalayer, before, after)
        self.feedback_message = (
            f"{self.name}: copied '{entry.semantic_type}' entry '{entry.id_}'"
            f" onto case '{entry.case_id}' (CM-23-016)"
        )
        self.logger.info("%s", self.feedback_message)
        return Status.SUCCESS

    def _refuse(
        self, entry: CaseLedgerEntry, exc: VultronEntryRefusedError
    ) -> Status:
        """Hold a refused entry's ``Announce`` and report the divergence.

        The entry is never patched over.  It extends this replica's chain and
        the case file is not past it, so no replay can fill the gap: the
        replica's case has diverged from the CASE_MANAGER's, and the
        CASE_MANAGER is told so with a ``LedgerEntryRefused/CaseDiverged``
        fault (SYNC-16-001).  The ``Announce`` is held as a forward gap is,
        and the fault is sent whether or not the holding area's bound let it
        be held.  Each replay of the held ``Announce`` that is refused again
        queues the same fault, under the same id, which the CASE_MANAGER
        drops as a repeat; the replay rate bound limits how often
        (SYNC-15-003).
        """
        assert self.datalayer is not None
        buffered = hold_received_announce(
            self.name, self.datalayer, self.activity, self.actor_id
        )
        self.refused_into_gap = buffered
        emit_ledger_entry_fault(
            self,
            self.activity,
            VULTRON_FAILURE_LEDGER_ENTRY_REFUSED_CASE_DIVERGED,
        )
        self.feedback_message = (
            f"{self.name}: entry '{entry.id_}' (log_index={entry.log_index})"
            f" does not apply to case '{entry.case_id}': {exc};"
            + (
                " its Announce is held for replay (ADR-0124)"
                if buffered
                else " the holding area bound dropped its Announce"
            )
        )
        self.logger.warning("%s", self.feedback_message)
        return Status.FAILURE


class IsEmbargoConsentEventNode(_SemanticTypeSetNode):
    """Precondition: SUCCESS when this log entry IS a consent-row entry.

    ``create_embargo_consent`` or ``update_embargo_consent``, the
    CASE_MANAGER's own entry for one consent row (ADR-0122, CLP-07-013).
    """

    matched_semantic_types = frozenset(CONSENT_ROW_VERBS)


class ApplyEmbargoConsentFromLedgerNode(ApplyEmbargoChangeFromLedgerNode):
    """Copy the consent row a ``Create``/``Update(EmbargoConsent)`` entry carries."""

    def _change(self, entry: CaseLedgerEntry) -> EmbargoChange:
        data = entry.payload_snapshot.get("object")
        if not isinstance(data, dict):
            raise TypeError("the entry carries no EmbargoConsent object")
        row = EmbargoConsent.model_validate(
            project_wire_snapshot_to_core(EmbargoConsent, data)
        )
        return ConsentRowChange(
            verb=CONSENT_ROW_VERBS[entry.semantic_type], row=row
        )


__all__ = [
    "ApplyEmbargoChangeFromLedgerNode",
    "ApplyEmbargoConsentFromLedgerNode",
    "IsEmbargoConsentEventNode",
]
