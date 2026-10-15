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
never patched over: the frame holds it in the actor-local gap buffer
(``LedgerGapBuffer``, keyed on its predecessor hash) and fails, so the entry
is not persisted (SYNC-12-001), and the receive path reports it deferred.
The entry extends the stored chain, so the gap drain that follows every
received announce for the case takes it again and retries it; it stays held
until this replica's case reaches the entry's start.  An entry this replica
had already applied, but not stored, is in place and passes as a no-op
(:func:`~vultron.core.models.embargo_apply.change_is_in_place`).

:class:`ApplyEmbargoConsentFromLedgerNode` is the first slot: the
CASE_MANAGER's ``Create(EmbargoConsent)`` and ``Update(EmbargoConsent)``
entries, each carrying one consent row in full.  The register-step slots of
the embargo acts subclass the same frame (#4714 – #4717).
"""

from __future__ import annotations

from typing import cast

from py_trees.common import Status
from py_trees.ports import NoDataAvailable, PortInformation

from vultron.core.behaviors.embargo_case_file import (
    read_embargo_case_file,
    save_case_file,
)
from vultron.core.behaviors.sync.nodes._helpers import _LedgerEffectNode
from vultron.core.behaviors.sync.nodes.event_conditions import (
    _EventTypeSetNode,
)
from vultron.core.models._helpers import project_wire_snapshot_to_core
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.embargo_apply import (
    ConsentRowChange,
    EmbargoChange,
    apply_embargo_change,
    change_is_in_place,
)
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.embargo_consent_event_types import (
    CONSENT_ROW_VERBS,
)
from vultron.core.models.ledger_gap_buffer import LedgerGapBuffer
from vultron.errors import VultronEntryRefusedError


class ApplyEmbargoChangeFromLedgerNode(_LedgerEffectNode):
    """Copy one embargo entry onto this replica's case file, or refuse it.

    Subclasses implement :meth:`_change`.  SUCCESS when the change is applied
    and saved, when it is already in place (a re-applied entry), or when this
    replica holds no copy of the case (Regime 2, ADR-0087).  FAILURE when the entry is malformed, or when the apply
    function refuses it; a refused entry is held in the gap buffer and
    :attr:`refused_into_gap` is set.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **_LedgerEffectNode.INPUT_PORTS,
        "gap_buffer": PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity", "gap_buffer": "/gap_buffer"}

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._gap_buffer: LedgerGapBuffer | None = None
        #: True after a run whose entry the apply function refused.
        self.refused_into_gap = False

    def initialise(self) -> None:
        super().initialise()
        self.refused_into_gap = False
        try:
            self._gap_buffer = cast(
                LedgerGapBuffer, self.get_input("gap_buffer")
            )
        except (NoDataAvailable, NotImplementedError):
            self._gap_buffer = None

    def _change(self, entry: CaseLedgerEntry) -> EmbargoChange:
        """The change *entry* carries.

        Raises:
            TypeError: the snapshot carries no object of the expected shape.
            ValueError: the carried object is not a valid change.
        """
        raise NotImplementedError

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        entry = self._get_entry()
        try:
            change = self._change(entry)
        except (TypeError, ValueError) as exc:
            self.feedback_message = (
                f"{self.name}: '{entry.event_type}' entry '{entry.id_}' does"
                f" not carry a valid change: {exc}"
            )
            self.logger.exception("%s", self.feedback_message)
            return Status.FAILURE

        if self._resolve_case_replica(entry.case_id) is None:
            return Status.SUCCESS  # Regime 2 (ADR-0087): partial replica

        before = read_embargo_case_file(self.datalayer, entry.case_id)
        if change_is_in_place(before, change):
            self.logger.debug(
                "%s: '%s' entry '%s' is already in place on case '%s' —"
                " idempotent no-op",
                self.name,
                entry.event_type,
                entry.id_,
                entry.case_id,
            )
            return Status.SUCCESS
        try:
            after = apply_embargo_change(before, change)
        except VultronEntryRefusedError as exc:
            return self._refuse(entry, exc)
        save_case_file(self.datalayer, before, after)
        self.feedback_message = (
            f"{self.name}: copied '{entry.event_type}' entry '{entry.id_}'"
            f" onto case '{entry.case_id}' (CM-23-016)"
        )
        self.logger.info("%s", self.feedback_message)
        return Status.SUCCESS

    def _refuse(
        self, entry: CaseLedgerEntry, exc: VultronEntryRefusedError
    ) -> Status:
        """Hold a refused entry for gap handling; never patch it over."""
        buffered = self._gap_buffer is not None and self._gap_buffer.buffer(
            entry
        )
        self.refused_into_gap = buffered
        self.feedback_message = (
            f"{self.name}: entry '{entry.id_}' (log_index={entry.log_index})"
            f" does not apply to case '{entry.case_id}': {exc};"
            + (
                " held in the gap buffer (ADR-0124)"
                if buffered
                else " no gap buffer holds it"
            )
        )
        self.logger.warning("%s", self.feedback_message)
        return Status.FAILURE


class IsEmbargoConsentEventNode(_EventTypeSetNode):
    """Precondition: SUCCESS when this log entry IS a consent-row entry.

    ``create_embargo_consent`` or ``update_embargo_consent``, the
    CASE_MANAGER's own entry for one consent row (ADR-0122, CLP-07-013).
    """

    matched_event_types = frozenset(CONSENT_ROW_VERBS)


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
            verb=CONSENT_ROW_VERBS[entry.event_type], row=row
        )


__all__ = [
    "ApplyEmbargoChangeFromLedgerNode",
    "ApplyEmbargoConsentFromLedgerNode",
    "IsEmbargoConsentEventNode",
]
