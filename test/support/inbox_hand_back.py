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

"""A recording ``InboxHandBackPort`` and a driver that delivers its queue.

Use-case tests construct a received use case directly, with no inbox in
front of it, so a buffered successor the tree hands back (SYNC-14-009) goes
nowhere unless the test delivers it.  :class:`RecordingInboxHandBack` records
each hand-back and runs nothing, which is what lets a test assert that no
second tree ran; :func:`deliver_handed_back` then plays the inbox loop's part,
delivering each recorded entry as the ``Announce(CaseLedgerEntry)`` the real
adapter queues.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

from vultron.adapters.driven.inbox_hand_back_adapter import (
    delivered_announce,
    hand_back_announce,
)
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.events.sync import AnnounceLogEntryReceivedEvent
from vultron.semantic_registry import extract_event


@dataclass(frozen=True)
class HandedBack:
    """One call to ``hand_back_ledger_entry``, as the port received it."""

    entry: CaseLedgerEntry
    case_manager_id: str
    receiving_actor_id: str


@dataclass
class RecordingInboxHandBack:
    """``InboxHandBackPort`` double: records each hand-back, runs nothing."""

    handed_back: list[HandedBack] = field(default_factory=list)
    _delivered: int = 0

    def hand_back_ledger_entry(
        self,
        entry: CaseLedgerEntry,
        case_manager_id: str,
        receiving_actor_id: str,
    ) -> None:
        self.handed_back.append(
            HandedBack(entry, case_manager_id, receiving_actor_id)
        )

    def take_pending(self) -> HandedBack | None:
        """The oldest hand-back not yet delivered, or ``None``."""
        if self._delivered >= len(self.handed_back):
            return None
        pending = self.handed_back[self._delivered]
        self._delivered += 1
        return pending


def handed_back_event(
    handed_back: HandedBack,
) -> AnnounceLogEntryReceivedEvent:
    """The event the inbox routes for *handed_back*, as the adapter wraps it.

    Delivered as the adapter holds it, with its body as received evidence.
    """
    activity = delivered_announce(
        hand_back_announce(
            handed_back.entry,
            handed_back.case_manager_id,
            handed_back.receiving_actor_id,
        )
    )
    event = cast(AnnounceLogEntryReceivedEvent, extract_event(activity))
    return event.model_copy(
        update={"receiving_actor_id": handed_back.receiving_actor_id}
    )


def deliver_handed_back(
    port: RecordingInboxHandBack,
    deliver: Callable[[AnnounceLogEntryReceivedEvent], object],
) -> int:
    """Deliver every pending hand-back, oldest first, as the inbox loop does.

    A delivered entry's own tree may hand back the next one, which is then
    delivered in turn.  Returns how many deliveries ran.
    """
    count = 0
    while (pending := port.take_pending()) is not None:
        deliver(handed_back_event(pending))
        count += 1
    return count
