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
"""Hand a buffered ledger successor back to the receiving actor's inbox."""

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
from vultron.core.models.ledger_gap_buffer import LedgerGapBuffer
from vultron.core.participants.authority import case_manager_address
from vultron.core.ports.inbox_hand_back import InboxHandBackPort
from vultron.core.sync_helpers import reconstruct_tail_hash
from vultron.errors import VultronValidationError, VultronWiringError

#: Blackboard key the received use cases write the hand-back port under.
INBOX_HAND_BACK_KEY = "inbox_hand_back"


class HandBackBufferedSuccessorNode(DataLayerActionWithPorts):
    """Hand the buffered successor of the local chain tail back to the inbox.

    Runs after the tree has committed a ledger entry (or seeded the case,
    which anchors the genesis hash).  If the actor-local gap buffer holds the
    entry whose ``prev_log_hash`` is the new tail, the node hands that one
    entry to the :class:`~vultron.core.ports.inbox_hand_back.InboxHandBackPort`
    as a delivery of its own, attributed to the case's CASE_MANAGER and
    addressed to the executing (receiving) actor (SYNC-14-009, ADR-0135).  It
    does not run the successor's tree: that delivery's own tree hands back the
    next successor, so the cascade (SYNC-14-003, SYNC-15-005) needs no loop.

    The node looks before it takes: the entry leaves the buffer only after
    the port has accepted it, so a wiring fault or an unresolvable
    CASE_MANAGER leaves it held.

    Outcomes:

    - No gap buffer, no genesis anchor yet, or no buffered successor:
      ``SUCCESS``, nothing to do.
    - A successor and no port: raises ``VultronWiringError``.  A missing port
      is a composition fault, never a reason to apply the entry inline.
    - A successor but no resolvable CASE_MANAGER: logs a warning, leaves the
      entry buffered and returns ``SUCCESS``.  The drain never guesses a
      sender; the CASE_MANAGER's replay remains the backstop (SYNC-15-001).
    - Otherwise: hands the entry back, removes it from the buffer,
      ``SUCCESS``.

    Args:
        case_id: The case whose buffer to look in.  ``None`` reads it from the
            ``CaseLedgerEntry`` carried by ``/activity``.
        name: Node name.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=False),
        "gap_buffer": PortInformation(data_type=object, required=False),
        INBOX_HAND_BACK_KEY: PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "activity": "/activity",
            "gap_buffer": "/gap_buffer",
            INBOX_HAND_BACK_KEY: f"/{INBOX_HAND_BACK_KEY}",
        }

    def __init__(
        self, case_id: str | None = None, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self.activity: object | None = None
        self._gap_buffer: LedgerGapBuffer | None = None
        self._hand_back: InboxHandBackPort | None = None

    def initialise(self) -> None:
        super().initialise()
        self.activity = self._try_get_input("activity")
        self._gap_buffer = cast(
            "LedgerGapBuffer | None", self._try_get_input("gap_buffer")
        )
        self._hand_back = cast(
            "InboxHandBackPort | None",
            self._try_get_input(INBOX_HAND_BACK_KEY),
        )

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        if self._gap_buffer is None:
            return Status.SUCCESS
        case_id = self._case_id or require_case_id_from_activity(
            self.activity, self.name
        )
        if self._gap_buffer.depth(case_id) == 0:
            return Status.SUCCESS
        try:
            tail_hash, _ = reconstruct_tail_hash(case_id, self.datalayer)
        except VultronValidationError:
            # No genesis anchor yet: nothing buffered can extend the chain.
            return Status.SUCCESS
        successor = self._gap_buffer.peek_next(case_id, tail_hash)
        if successor is None:
            return Status.SUCCESS
        if self._hand_back is None:
            raise VultronWiringError(
                f"{self.name}: {INBOX_HAND_BACK_KEY} must be injected to hand"
                f" buffered ledger entry '{successor.id_}' back to the inbox"
                " (SYNC-14-009)"
            )
        if not self.actor_id:
            raise VultronWiringError(
                f"{self.name}: no executing actor to hand ledger entry"
                f" '{successor.id_}' back to"
            )
        case_manager_id = case_manager_address(self.datalayer, case_id)
        if case_manager_id is None:
            self.logger.warning(
                "%s: case '%s' has no resolvable CASE_MANAGER; buffered"
                " ledger entry '%s' stays held until the CASE_MANAGER"
                " replays it (SYNC-14-009, SYNC-15-001)",
                self.name,
                case_id,
                successor.id_,
            )
            return Status.SUCCESS
        self._hand_back.hand_back_ledger_entry(
            successor,
            case_manager_id=case_manager_id,
            receiving_actor_id=self.actor_id,
        )
        self._gap_buffer.take_next(case_id, tail_hash)
        self.logger.info(
            "%s: handed buffered ledger entry '%s' (log_index=%d) for case"
            " '%s' back to actor '%s' inbox as an Announce from '%s'",
            self.name,
            successor.id_,
            successor.log_index,
            case_id,
            self.actor_id,
            case_manager_id,
        )
        return Status.SUCCESS


__all__ = ["HandBackBufferedSuccessorNode", "INBOX_HAND_BACK_KEY"]
