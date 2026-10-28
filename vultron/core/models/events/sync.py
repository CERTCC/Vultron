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

from typing import Literal, cast

from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.events.base import (
    LedgerPositionedEvent,
    MessageSemantics,
    VultronEvent,
)
from vultron.core.models.ledger_position import (
    EMPTY_LEDGER_LOG_INDEX,
    LedgerPosition,
)


class AnnounceLogEntryReceivedEvent(VultronEvent):
    """CaseActor announced a canonical CaseLedgerEntry for log replication.

    Spec: SYNC-02-003, SYNC-03-001, SYNC-03-002, SYNC-03-003.
    """

    semantic_type: Literal[MessageSemantics.ANNOUNCE_CASE_LEDGER_ENTRY] = (
        MessageSemantics.ANNOUNCE_CASE_LEDGER_ENTRY
    )

    @property
    def log_entry(self) -> CaseLedgerEntry | None:
        """Return the received :class:`CaseLedgerEntry`, or ``None``."""
        if self.object_ is None:
            return None
        return cast(CaseLedgerEntry, self.object_)

    @property
    def log_entry_id(self) -> str | None:
        """Return the ID of the received log entry."""
        return self.object_id


class RejectLogEntryReceivedEvent(VultronEvent):
    """Participant rejected an ``Announce(CaseLedgerEntry)`` due to hash-chain mismatch.

    ``ledger_position`` is the sender's ledger tail, which the activity
    states as ``ledgerPosition`` (SYNC-18-001): the last entry it accepted,
    or index -1 and the genesis hash when it holds the case but no entry.
    A peer that does not hold the case yet holds no ledger to state, so its
    ``Reject`` carries none (SYNC-18-001) and the position is ``None``; the
    extractor still refuses a malformed one (SYNC-18-003).

    Spec: SYNC-03-001, SYNC-03-002, SYNC-16-007, SYNC-18-001.
    """

    semantic_type: Literal[MessageSemantics.REJECT_CASE_LEDGER_ENTRY] = (
        MessageSemantics.REJECT_CASE_LEDGER_ENTRY
    )
    ledger_position: LedgerPosition | None = None

    @property
    def rejected_entry(self) -> CaseLedgerEntry | None:
        """Return the rejected :class:`CaseLedgerEntry`, or ``None``."""
        if self.object_ is None:
            return None
        return cast(CaseLedgerEntry, self.object_)

    @property
    def rejected_case_id(self) -> str | None:
        """The case the rejection is about, or ``None``.

        The rejected entry's case, or, for the Reject that names no entry
        because the peer holds none and asks for a replay from genesis, the
        case its ``target`` names (SYNC-16-007).
        """
        entry = self.rejected_entry
        if entry is not None:
            return entry.case_id
        return self.target_id

    @property
    def replay_case_id(self) -> str | None:
        """The case whose ledger the peer asks to have replayed.

        The name the replay nodes read on every activity that can start a
        replay (``Reject`` and ``Read`` of a ``CaseLedgerEntry``): here it is
        :attr:`rejected_case_id`.
        """
        return self.rejected_case_id

    @property
    def last_accepted_hash(self) -> str:
        """Return the hash of the last entry the peer reports it accepted.

        ``""`` (empty string) when the peer states no position, or one at
        index -1, because it holds no entry: replay then starts from the
        beginning of the recorded projection (CLP-08-005, SYNC-16-007).
        """
        position = self.ledger_position
        if position is None or position.log_index == EMPTY_LEDGER_LOG_INDEX:
            return ""
        return position.entry_hash


class ReadLogEntryReceivedEvent(LedgerPositionedEvent):
    """A participant stated its ledger position: ``Read(CaseLedgerEntry)``.

    The ``object`` names, by reference, the last canonical entry the sender
    has applied for the case; the ``context`` names the case, and
    ``ledger_position`` carries that entry's ``log_index`` and
    ``entry_hash``, parsed at the edge (SYNC-17-001, ADR-0032).  The entry
    it names is the sender's tail, so the position it states is the one
    every case activity states (SYNC-18-001).  The
    CASE_MANAGER judges the position against its own ledger: it never reads
    the entry from the activity.

    Spec: SYNC-17-001 through SYNC-17-006.
    """

    semantic_type: Literal[MessageSemantics.READ_CASE_LEDGER_ENTRY] = (
        MessageSemantics.READ_CASE_LEDGER_ENTRY
    )

    @property
    def stated_entry_id(self) -> str | None:
        """The id of the entry the sender names as the last it applied."""
        return self.object_id

    @property
    def replay_case_id(self) -> str | None:
        """The case the stated position is in, from the ``context``."""
        return self.context_id

    @property
    def last_accepted_hash(self) -> str:
        """The ``entry_hash`` of the entry the sender states it applied last.

        The name the replay nodes read for the position a replay starts
        after, as they read it on a ``Reject(CaseLedgerEntry)``.
        """
        return self.ledger_position.entry_hash
