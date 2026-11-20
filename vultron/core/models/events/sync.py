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
"""Per-semantic inbound domain event types for LedgerFanout/LedgerReconciliation log replication."""

from typing import ClassVar, Literal, cast

from vultron.core.models.case_ledger_entry import (
    CaseLedgerEntry,
    case_ledger_id,
)
from vultron.core.models.events.base import (
    LedgerPositionedEvent,
    MessageSemantics,
    VultronEvent,
)
from vultron.core.models.ledger_position import (
    LedgerPosition,
    accepted_entry_hash,
)
from vultron.errors import VultronCanonicalEntryError


class AddLogEntryReceivedEvent(VultronEvent):
    """The CASE_MANAGER added a committed CaseLedgerEntry to the case's ledger.

    Received as ``Add(CaseLedgerEntry, target=<case>/ledger)``, with
    ``context`` the case and ``inReplyTo`` the committed act (ADR-0204).  An
    ``Add`` that names another ledger, another case or another act is
    refused at the parse edge, so core reads all three from the entry
    (ADR-0032).

    Spec: SYNC-02-003, SYNC-02-008, SYNC-02-010, SYNC-03-001, SYNC-03-002,
    SYNC-03-003.
    """

    semantic_type: Literal[
        MessageSemantics.ADD_CASE_LEDGER_ENTRY_TO_LEDGER
    ] = MessageSemantics.ADD_CASE_LEDGER_ENTRY_TO_LEDGER
    required_slots: ClassVar[tuple[str, ...]] = (
        "log_entry",
        "ledger_id",
        "acknowledged_act_id",
    )

    @property
    def log_entry(self) -> CaseLedgerEntry:
        """The received :class:`CaseLedgerEntry`, inline in the Add."""
        entry = self._required(
            "log_entry", cast("CaseLedgerEntry | None", self.object_)
        )
        if self.context_id != entry.case_id:
            raise ValueError(
                f"{type(self).__name__} {self.activity_id!r}: context names"
                f" {self.context_id!r}, not the entry's case"
                f" {entry.case_id!r} (SYNC-02-008)"
            )
        return entry

    @property
    def log_entry_id(self) -> str | None:
        """Return the ID of the received log entry."""
        return self.object_id

    @property
    def ledger_id(self) -> str:
        """The ledger the entry is added to: its case's ledger (SYNC-02-006)."""
        ledger = self._required("ledger_id", self.target_id)
        expected = case_ledger_id(self.log_entry.case_id)
        if ledger != expected:
            raise ValueError(
                f"{type(self).__name__} {self.activity_id!r}: target names"
                f" {ledger!r}, not the entry's ledger {expected!r}"
                " (SYNC-02-008)"
            )
        return ledger

    @property
    def acknowledged_act_id(self) -> str:
        """The act the entry commits, which the Add names in ``inReplyTo``.

        The ``Add`` is that act's positive acknowledgement (SYNC-02-007).
        """
        act_id = self._required("acknowledged_act_id", self.in_reply_to)
        try:
            committed = self.log_entry.committed_act_id()
        except VultronCanonicalEntryError as exc:
            raise ValueError(str(exc)) from exc
        if act_id != committed:
            raise ValueError(
                f"{type(self).__name__} {self.activity_id!r}: inReplyTo names"
                f" {act_id!r}, not the committed act {committed!r}"
                " (SYNC-02-010)"
            )
        return act_id


class RejectLogEntryReceivedEvent(VultronEvent):
    """Participant rejected an ``Add(CaseLedgerEntry)``: the gap NAK.

    The ``object`` is the entry the participant could not apply, and
    ``inReplyTo`` names the ``Add`` that carried it (SYNC-03-001, ADR-0204).
    ``ledger_position`` is the sender's ledger tail, which the activity
    states as ``ledgerPosition`` (SYNC-18-001): the last entry it accepted,
    or index -1 and the genesis hash when it holds the case but no entry.
    A peer that does not hold the case yet holds no ledger to state, so its
    ``Reject`` carries none (SYNC-18-016) and the position is ``None``; the
    extractor still refuses a malformed one (SYNC-18-003).

    Spec: SYNC-03-001, SYNC-03-002, SYNC-16-007, SYNC-18-001, SYNC-18-016.
    """

    semantic_type: Literal[MessageSemantics.REJECT_CASE_LEDGER_ENTRY] = (
        MessageSemantics.REJECT_CASE_LEDGER_ENTRY
    )
    ledger_position: LedgerPosition | None = None
    required_slots: ClassVar[tuple[str, ...]] = ("rejected_entry",)

    @property
    def rejected_entry(self) -> CaseLedgerEntry:
        """The rejected :class:`CaseLedgerEntry`, inline in the Reject."""
        return self._required(
            "rejected_entry", cast("CaseLedgerEntry | None", self.object_)
        )

    @property
    def rejected_case_id(self) -> str:
        """The case the rejection is about: the rejected entry's case."""
        return self._required("rejected_case_id", self.rejected_entry.case_id)

    @property
    def replay_case_id(self) -> str:
        """The case whose ledger the peer asks to have replayed.

        The name the replay nodes read on every activity that can start a
        replay (``Reject`` of a ``CaseLedgerEntry`` and ``Read`` of a case's
        ledger): here it is :attr:`rejected_case_id`.
        """
        return self.rejected_case_id

    @property
    def last_accepted_hash(self) -> str:
        """Return the hash of the last entry the peer reports it accepted.

        ``""`` (empty string) when the peer states no position, or one at
        index -1, because it holds no entry: replay then starts from the
        beginning of the recorded projection (CLP-08-008).
        """
        return accepted_entry_hash(self.ledger_position)


class ReadLedgerReceivedEvent(LedgerPositionedEvent):
    """A participant stated its ledger position: ``Read(<case>/ledger)``.

    The ``object`` is the case's ledger, ``<case>/ledger``; the ``context``
    names the case, and ``ledger_position`` carries the sender's tail,
    parsed at the edge (SYNC-17-001, ADR-0032, ADR-0204): the last entry it
    holds, or index -1 and the case's genesis hash when it holds none
    (SYNC-16-027).  It is the position every case activity states
    (SYNC-18-001).  The CASE_MANAGER judges the position against its own
    ledger and replays every entry after it.

    Spec: SYNC-17-001 through SYNC-17-006, SYNC-16-027.
    """

    semantic_type: Literal[MessageSemantics.READ_CASE_LEDGER] = (
        MessageSemantics.READ_CASE_LEDGER
    )
    required_slots: ClassVar[tuple[str, ...]] = (
        "replay_case_id",
        "ledger_id",
    )

    @property
    def replay_case_id(self) -> str:
        """The case the stated position is in, from the ``context``."""
        return self._required("replay_case_id", self.context_id)

    @property
    def ledger_id(self) -> str:
        """The ledger the ``Read`` names: its case's ledger (SYNC-17-001)."""
        ledger = self._required("ledger_id", self.object_id)
        expected = case_ledger_id(self.replay_case_id)
        if ledger != expected:
            raise ValueError(
                f"{type(self).__name__} {self.activity_id!r}: object names"
                f" {ledger!r}, not the case's ledger {expected!r}"
                " (SYNC-17-001)"
            )
        return ledger
