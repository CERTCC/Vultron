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
"""Replay the held ``Announce`` of the chain tail's successor (SYNC-14-009)."""

from __future__ import annotations

from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.sync.nodes.chain import (
    require_case_id_from_activity,
)
from vultron.core.ports.inbox_replay import InboxReplayPort
from vultron.core.services.held_ledger_announces import (
    held_ledger_announces,
    held_successor,
    holds_held_body,
    release_held,
)
from vultron.core.sync_helpers import reconstruct_tail_hash
from vultron.errors import VultronValidationError, VultronWiringError

#: Blackboard key the received use cases write the replay port under.
INBOX_REPLAY_KEY = "inbox_replay"


class ReplayHeldSuccessorNode(DataLayerActionWithPorts):
    """Replay the held ``Announce`` whose entry extends the local chain tail.

    Runs after the tree has committed a ledger entry (or found it stored, or
    seeded the case, which anchors the genesis hash).  If this actor holds
    the ``Announce(CaseLedgerEntry)`` whose entry's ``prev_log_hash`` is the
    new tail, the node asks the
    :class:`~vultron.core.ports.inbox_replay.InboxReplayPort` to replay that
    ``Announce``, the one that was received, through this actor's inbox as a
    delivery of its own (SYNC-14-009, ADR-0135).  It does not run the
    successor's tree: that delivery's own tree replays the next one, so the
    cascade (SYNC-14-003, SYNC-15-005) needs no loop.

    The node looks before it takes: the index row is dropped only after the
    port has queued the replay, so a wiring fault leaves the ``Announce``
    held.

    Outcomes:

    - Nothing held for the case, no genesis anchor yet, or no held
      successor: ``SUCCESS``, nothing to do.
    - A held successor whose body is gone: drops the index row with a
      warning, ``SUCCESS``; the Reject sent when it was held recovers the
      entry (SYNC-14-002).
    - A successor and no port: raises ``VultronWiringError``.  A missing port
      is a composition fault, never a reason to apply the entry inline.
    - Otherwise: queues the replay, drops the index row, ``SUCCESS``.

    Args:
        case_id: The case whose held ``Announce``\\ s to look in.  ``None``
            reads it from the ``CaseLedgerEntry`` carried by ``/activity``.
        name: Node name.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=False),
        INBOX_REPLAY_KEY: PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "activity": "/activity",
            INBOX_REPLAY_KEY: f"/{INBOX_REPLAY_KEY}",
        }

    def __init__(
        self, case_id: str | None = None, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self.activity: object | None = None
        self._replay: InboxReplayPort | None = None

    def initialise(self) -> None:
        super().initialise()
        self.activity = self._try_get_input("activity")
        self._replay = cast(
            "InboxReplayPort | None", self._try_get_input(INBOX_REPLAY_KEY)
        )

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        case_id = self._case_id or require_case_id_from_activity(
            self.activity, self.name
        )
        if not held_ledger_announces(self.datalayer, case_id):
            return Status.SUCCESS
        try:
            tail_hash, _ = reconstruct_tail_hash(case_id, self.datalayer)
        except VultronValidationError:
            # No genesis anchor yet: nothing held can extend the chain.
            return Status.SUCCESS
        successor = held_successor(self.datalayer, case_id, tail_hash)
        if successor is None:
            return Status.SUCCESS
        if not holds_held_body(self.datalayer, successor):
            # An index row whose body is gone can never replay; dropping it
            # keeps the case's drain moving, and the Reject sent when the
            # Announce was held still recovers the entry (SYNC-14-002).
            release_held(self.datalayer, successor)
            self.logger.warning(
                "%s: held Announce '%s' of ledger entry '%s' (case '%s') has"
                " no held body; dropped its index row, the CASE_MANAGER's"
                " replay recovers the entry (SYNC-14-002)",
                self.name,
                successor.activity_id,
                successor.entry_id,
                case_id,
            )
            return Status.SUCCESS
        if self._replay is None:
            raise VultronWiringError(
                f"{self.name}: {INBOX_REPLAY_KEY} must be injected to replay"
                f" the held Announce '{successor.activity_id}' of ledger"
                f" entry '{successor.entry_id}' (SYNC-14-009)"
            )
        self._replay.replay_held(successor.activity_id)
        release_held(self.datalayer, successor)
        self.logger.info(
            "%s: replaying held Announce '%s' of ledger entry '%s'"
            " (log_index=%d) for case '%s' through actor '%s' inbox",
            self.name,
            successor.activity_id,
            successor.entry_id,
            successor.log_index,
            case_id,
            self.actor_id,
        )
        return Status.SUCCESS


__all__ = ["INBOX_REPLAY_KEY", "ReplayHeldSuccessorNode"]
