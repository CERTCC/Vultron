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
"""Nodes for a participant's ledger position statement (SYNC-17, ADR-0155).

A participant states how far it has applied a case's ledger by sending the
case's CASE_MANAGER ``Read(CaseLedgerEntry)`` naming its tail entry
(SYNC-17-001).  The CASE_MANAGER first checks that the stated position is a
position in its own ledger (:class:`CheckStatedPositionInLedgerNode`,
SYNC-17-005); the record and the replay that answer it are the replication
nodes a ``Reject(CaseLedgerEntry)`` already runs (SYNC-17-003, SYNC-17-004).

:class:`StateLedgerPositionsNode` is the sending side: it queues one
``Read(CaseLedgerEntry)`` for each case the executing actor holds a replica
of (SYNC-17-007).
"""

from __future__ import annotations

import logging
from typing import cast

from py_trees.common import Status
from py_trees.ports import NoDataAvailable

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.sync.nodes.replay_case import replay_case_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.participants.recipients import closure_recorded
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.sync_helpers import sorted_case_ledger_entries
from vultron.errors import VultronError, VultronWiringError

logger = logging.getLogger(__name__)


def _stated_position(activity: object, node_name: str) -> LedgerPosition:
    """The ``LedgerPosition`` a ``Read(CaseLedgerEntry)`` states.

    Raises ``VultronError`` when the activity carries none (BT-HELPER-01).
    """
    position = getattr(activity, "ledger_position", None)
    if isinstance(position, LedgerPosition):
        return position
    raise VultronError(f"{node_name}: activity states no ledger position")


def ledger_entry_at(
    entries: list[CaseLedgerEntry], position: LedgerPosition
) -> CaseLedgerEntry | None:
    """The entry of *entries* at *position*'s index, or ``None``."""
    return next(
        (entry for entry in entries if entry.log_index == position.log_index),
        None,
    )


class CheckStatedPositionInLedgerNode(DataLayerConditionWithPorts):
    """Pass only a stated position that names an entry of this ledger.

    The CASE_MANAGER answers a ``Read(CaseLedgerEntry)`` only when the
    position it states is one its own ledger holds: an entry at the stated
    ``log_index`` whose id is the stated ``object`` and whose hash is the
    stated ``entry_hash``.  Any other position is not a lag: replaying from
    a guessed point would send a suffix the replica cannot anchor.  So it is
    logged at WARNING with the sender and the position, and the node fails
    before any replication state is recorded or any entry sent
    (SYNC-17-005).  A replica whose case has diverged reports it by
    SYNC-16-001.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity"}

    def initialise(self) -> None:
        super().initialise()
        self.activity = self.get_input("activity")

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        activity = self.activity
        case_id = replay_case_id(activity, self.name)
        position = _stated_position(activity, self.name)
        stated_id = getattr(activity, "stated_entry_id", None)
        held = ledger_entry_at(
            sorted_case_ledger_entries(
                cast(CasePersistence, self.datalayer), case_id
            ),
            position,
        )
        if held is None:
            problem = "names an entry this ledger does not hold"
        elif held.id_ != stated_id:
            problem = (
                f"names entry '{stated_id}', but index holds '{held.id_}'"
            )
        elif held.entry_hash != position.entry_hash:
            problem = (
                f"names an index at which this ledger's entry has hash"
                f" {held.entry_hash:.16}…"
            )
        else:
            return Status.SUCCESS
        self.feedback_message = (
            f"stated ledger position (log_index={position.log_index},"
            f" entry_hash={position.entry_hash:.16}…) {problem}"
        )
        self.logger.warning(
            "%s: Read(CaseLedgerEntry) '%s' from '%s' for case '%s': stated"
            " position (object='%s', log_index=%d, entry_hash=%.16s…) %s;"
            " nothing recorded or sent (SYNC-17-005)",
            self.name,
            getattr(activity, "activity_id", None),
            getattr(activity, "actor_id", None),
            case_id,
            stated_id,
            position.log_index,
            position.entry_hash,
            problem,
        )
        return Status.FAILURE


class StateLedgerPositionsNode(DataLayerActionWithPorts):
    """Queue ``Read(CaseLedgerEntry)`` for each case replica the actor holds.

    For each ``VulnerabilityCase`` in the executing actor's store whose
    CASE_MANAGER is another actor, the participant names the last entry its
    replica has stored and sends it to that CASE_MANAGER (SYNC-17-001,
    SYNC-17-007).  It sends nothing for a case it manages, a case naming no
    CASE_MANAGER, a case whose roster does not list it, a case whose ledger
    it holds no entry of (it has no entry to name), or a case that records
    its own closure: closure is final, and the CASE_MANAGER refuses a closed
    sender (CM-23-018).  An inert participant, removed or not yet a
    signatory, still states its position.  Its replica learns that it is
    inert from ledger entries, and the entry that made it active again may be
    the one it lost; the CASE_MANAGER refuses the statement of a participant
    that is still inert (SYNC-17-002).  An unlisted actor is different: a
    participant's replica is seeded from a copy that already lists it, so a
    case whose roster lacks the actor is not a replica it participates in,
    and the CASE_MANAGER would refuse its statement (SYNC-17-002).

    ``sent`` counts the statements queued, for the caller's log.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "sync_port": PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"sync_port": "/sync_port"}

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._sync_port: SyncActivityPort | None = None
        self.sent = 0

    def initialise(self) -> None:
        super().initialise()
        self.sent = 0
        try:
            self._sync_port = cast(
                SyncActivityPort, self.get_input("sync_port")
            )
        except (NoDataAvailable, NotImplementedError):
            self._sync_port = None

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None
        if self._sync_port is None:
            raise VultronWiringError(
                f"{self.name}: sync_port must be injected to state ledger"
                " positions"
            )
        dl = cast(CasePersistence, self.datalayer)
        for case in dl.list_objects("VulnerabilityCase"):
            if not isinstance(case, VulnerabilityCase):
                continue
            manager_id = resolve_case_manager_id(case, dl)
            if manager_id is None or manager_id == self.actor_id:
                continue
            if self.actor_id not in case.actor_participant_index:
                continue
            if closure_recorded(case, dl, self.actor_id):
                continue
            entries = sorted_case_ledger_entries(dl, case.id_)
            if not entries:
                continue
            tail = entries[-1]
            self._sync_port.send_read_ledger_entry(
                entry=tail, actor_id=self.actor_id, to=[manager_id]
            )
            self.sent += 1
            self.logger.info(
                "%s: stated ledger position of case '%s' (log_index=%d) to"
                " CASE_MANAGER '%s' (SYNC-17-007)",
                self.name,
                case.id_,
                tail.log_index,
                manager_id,
            )
        return Status.SUCCESS
