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

"""A recording ``InboxReplayPort``, and a driver that delivers what it queued.

Use-case tests construct a received use case directly, with no inbox in
front of it, so a held ``Announce(CaseLedgerEntry)`` the tree replays
(SYNC-14-009) goes nowhere unless the test delivers it.
:class:`RecordingInboxReplay` records each replay and runs nothing, which is
what lets a test assert that no second tree ran; :func:`deliver_replayed` then
plays the inbox loop's part, rebuilding each held ``Announce`` from the body
held for it, as the inbox replay does, and delivering it.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, cast

from test.support.received import received_event
from vultron.adapters.inbox_staging import InlineObjectStaging
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.events.sync import AnnounceLogEntryReceivedEvent
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.services.held_ledger_announces import (
    held_ledger_announces,
    hold_ledger_announce,
)
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import announce_log_entry_activity
from vultron.wire.as2.vocab.objects.case_ledger_entry import as_CaseLedgerEntry


def ledger_announce_event(
    entry: CaseLedgerEntry, *, actor: str, to: str
) -> AnnounceLogEntryReceivedEvent:
    """The received ``Announce`` of *entry* from *actor* to *to*, delivered.

    It carries its body as received evidence, as the inbox hands it on, and
    names *to* as the receiving actor.
    """
    activity = announce_log_entry_activity(
        as_CaseLedgerEntry.model_validate(entry.model_dump(mode="json")),
        actor=actor,
        to=[to],
    )
    return cast(
        AnnounceLogEntryReceivedEvent,
        received_event(activity, receiving_actor_id=to),
    )


@dataclass
class RecordingInboxReplay:
    """``InboxReplayPort`` double: records each replay, runs nothing."""

    replayed: list[str] = field(default_factory=list)
    _delivered: int = 0

    def replay_held(self, activity_id: str) -> None:
        self.replayed.append(activity_id)

    def take_pending(self) -> str | None:
        """The oldest replay not yet delivered, or ``None``."""
        if self._delivered >= len(self.replayed):
            return None
        pending = self.replayed[self._delivered]
        self._delivered += 1
        return pending


def replayed_event(
    dl: Any, activity_id: str, receiving_actor_id: str
) -> AnnounceLogEntryReceivedEvent:
    """The event the inbox routes when it replays the held *activity_id*.

    Rebuilt from the body held for it, as the inbox replay does, so it
    carries the first delivery's received evidence (VM-08-002); the held
    record is released.
    """
    activity = InlineObjectStaging(dl).rehydrate_deferred(activity_id)
    assert activity is not None, f"nothing holds {activity_id}"
    event = cast(AnnounceLogEntryReceivedEvent, extract_event(activity))
    return event.model_copy(update={"receiving_actor_id": receiving_actor_id})


def deliver_replayed(
    port: RecordingInboxReplay,
    dl: Any,
    receiving_actor_id: str,
    deliver: Callable[[AnnounceLogEntryReceivedEvent], object],
) -> int:
    """Deliver every pending replay, oldest first, as the inbox loop does.

    A delivered entry's own tree may replay the next one, which is then
    delivered in turn.  Returns how many deliveries ran.
    """
    count = 0
    while (pending := port.take_pending()) is not None:
        deliver(replayed_event(dl, pending, receiving_actor_id))
        count += 1
    return count


def archive_event(dl: Any, event: AnnounceLogEntryReceivedEvent) -> None:
    """Archive *event*'s ``Announce`` in *dl* as intake does (CLP-10-017)."""
    assert event.received_evidence is not None
    dl.save(
        ReceivedActivityRecord(
            activity_id=event.activity_id,
            received_body=event.received_evidence,
        )
    )


def hold_received(dl: Any, event: AnnounceLogEntryReceivedEvent) -> None:
    """Hold *event*'s ``Announce`` in *dl* as an earlier delivery would have.

    Archives it as intake does, then holds it (SYNC-14-001).
    """
    entry = event.log_entry
    assert entry is not None
    archive_event(dl, event)
    assert hold_ledger_announce(dl, entry, event.activity_id)


def held_depth(dl: Any, case_id: str) -> int:
    """How many ``Announce``\\ s *dl* holds for *case_id*."""
    return len(held_ledger_announces(dl, case_id))
