#!/usr/bin/env python
#
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
"""The CASE_MANAGER's report of a replica's hash-mismatch fault (SYNC-03-010).

A replica that refuses a copied entry whose content does not reproduce its
stated hash sends the CASE_MANAGER ``Create(ProcessingFault)`` of class
``LedgerEntryRefused/HashMismatch`` (SYNC-03-007).  Neither a replay nor a
re-seed can heal it, since both resend the same content, so the CASE_MANAGER
only makes the problem visible: :class:`ReportHashMismatchNode` logs the fault
at ERROR and re-checks this store's own copy of the named entry, so the log
says which side is broken (SYNC-03-008, SYNC-03-010).
"""

from __future__ import annotations

from enum import StrEnum
from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.models.case_ledger import ledger_entry_hash_intact
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.ports.case_persistence import CasePersistence

__all__ = ["OwnCopyCheck", "ReportHashMismatchNode", "check_own_copy"]


class OwnCopyCheck(StrEnum):
    """What the CASE_MANAGER found when it re-checked its own copy."""

    INTACT = "intact"
    """Its stored copy reproduces its hash: the replica's copy is broken."""
    NOT_INTACT = "not intact"
    """Its stored copy does not reproduce its hash: its own ledger is broken."""
    NO_STORED_COPY = "no stored copy"
    """It holds no stored copy of the named entry."""


def check_own_copy(datalayer: CasePersistence, entry_id: str) -> OwnCopyCheck:
    """Re-check this store's own copy of ledger entry *entry_id*.

    Uses the one hash predicate, :func:`ledger_entry_hash_intact`, the check
    a replica runs on receipt (SYNC-03-006).  Read-only.

    Spec: SYNC-03-010.
    """
    stored = datalayer.read(entry_id)
    if not isinstance(stored, CaseLedgerEntry):
        return OwnCopyCheck.NO_STORED_COPY
    if ledger_entry_hash_intact(stored):
        return OwnCopyCheck.INTACT
    return OwnCopyCheck.NOT_INTACT


_VERDICT: dict[OwnCopyCheck, str] = {
    OwnCopyCheck.INTACT: (
        "this CASE_MANAGER's stored copy is intact, so the copy the replica"
        " received is broken: suspect the wire rendering or parsing"
    ),
    OwnCopyCheck.NOT_INTACT: (
        "this CASE_MANAGER's stored copy does not reproduce its hash either:"
        " this CASE_MANAGER's own ledger is broken"
    ),
    OwnCopyCheck.NO_STORED_COPY: (
        "this CASE_MANAGER holds no stored copy of the entry, so it cannot"
        " say which side is broken"
    ),
}


class ReportHashMismatchNode(DataLayerActionWithPorts):
    """Log a replica's hash-mismatch fault at ERROR, with a self-check.

    *refused_entry* is the entry the fault's ``inReplyTo`` ``Announce``
    (*announce_id*) carried; *peer_id* is the replica that refused it.  The
    node re-checks this store's own copy of that entry
    (:func:`check_own_copy`) and logs one ERROR record naming the case, the
    ``Announce``, the entry, the sender and the result, kept in
    :attr:`own_copy`.

    Writes nothing, sends nothing and always returns SUCCESS once it has
    run: a hash mismatch is answered by no replay and no re-seed
    (SYNC-03-008), and the replay cooldown alone bounds the loop it leaves
    (SYNC-15-013).  The CASE_MANAGER's own act; it belongs inside a
    CASE_MANAGER gate (BT-17-008).

    Spec: SYNC-03-008, SYNC-03-010.
    """

    def __init__(
        self,
        refused_entry: CaseLedgerEntry,
        *,
        peer_id: str,
        announce_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.refused_entry = refused_entry
        self.peer_id = peer_id
        self.announce_id = announce_id
        self.own_copy: OwnCopyCheck | None = None
        """The result of the last run's self-check; ``None`` before one."""

    def update(self) -> Status:
        self.own_copy = None
        if (f := self._require_datalayer()) is not None:
            return f
        entry = self.refused_entry
        self.own_copy = check_own_copy(
            cast(CasePersistence, self.datalayer), entry.id_
        )
        self.logger.error(
            "%s: peer '%s' refused ledger entry '%s' (log_index %d) of case"
            " '%s', sent in Announce '%s', because its content does not"
            " reproduce its hash (SYNC-03-007). Self-check: %s; %s. Nothing"
            " is replayed or re-seeded for it (SYNC-03-008, SYNC-03-010)",
            self.name,
            self.peer_id,
            entry.id_,
            entry.log_index,
            entry.case_id,
            self.announce_id,
            self.own_copy.value,
            _VERDICT[self.own_copy],
        )
        return Status.SUCCESS
