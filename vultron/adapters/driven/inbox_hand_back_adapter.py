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

"""Adapter implementing :class:`~vultron.core.ports.inbox_hand_back.InboxHandBackPort`.

Hands a buffered ledger entry back to the receiving actor's own inbox as a
delivery of its own (SYNC-14-009, ADR-0135).  It wraps the entry in an
``Announce(CaseLedgerEntry)`` attributed to the case's CASE_MANAGER and
addressed to the receiving actor, holds it in that actor's store the way the
inbox holds a deferred delivery (a ``DeferredInboxActivity`` keyed by the
receiver, never a row under the activity's own id, DL-06-006) and appends its
id to the actor's inbox queue.

That queue is the inbox's existing scheduling path: the delivery that made the
entry appliable is still running when the port is called, and once it ends
``run_inbox_pipeline`` pops the queued id and replays the held activity through
``process_payload`` under the same actor lock (IO-02-003, BT-11-001).  The
older ``inbox_handler`` queue worker also drains the queue, through its own
dispatch step rather than ``process_payload``, and rebuilds from the same
record.  No new concurrency mechanism is involved, and the handed-back entry
takes the same rebuild, route and tree path as a deferred delivery
(SYNC-14-008).  The entry itself is held inline in the Announce, never on its
own: only the replica's ``PersistReceivedLogEntry`` step writes a ledger entry
(SYNC-13-002).
"""

import logging
from collections.abc import Callable

from vultron.adapters.driven.sync_activity_adapter import (
    ledger_entry_to_wire,
)
from vultron.core.models.activity_ids import derived_activity_id
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.ports.datalayer import DataLayer
from vultron.wire.as2.factories import announce_log_entry_activity
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Announce,
)

#: Holds an activity for the inbox replay under the receiver's key, returning
#: whether it was newly held (a held copy is kept); the driving side's
#: ``inbox_staging.hold_activity`` (DL-06-006).
ActivityHolder = Callable[[DataLayer, as_Activity], bool]

logger = logging.getLogger(__name__)

#: Kind label for the derived id of a handed-back Announce (ID-04-004).
_HAND_BACK_ID_KIND = "ledger-entry-hand-back"


def hand_back_activity_id(receiving_actor_id: str, entry_id: str) -> str:
    """The id of the Announce that hands *entry_id* back to the receiver.

    Derived, not random, so handing the same entry back twice names the same
    delivery (ID-04-004).
    """
    return derived_activity_id(
        _HAND_BACK_ID_KIND, receiving_actor_id, entry_id
    )


def hand_back_announce(
    entry: CaseLedgerEntry, case_manager_id: str, receiving_actor_id: str
) -> as_Announce:
    """The ``Announce(CaseLedgerEntry)`` that carries *entry* back in.

    It is attributed to the CASE_MANAGER even though the receiver builds it:
    the buffer holds the entry, not the Announce that carried it, and the
    CASE_MANAGER is the one sender a replica applies entries from (SYNC-14-009,
    ADR-0135).  It is an inbox envelope, never a ledger entry, so the replica
    still mints nothing in the ledger (CLP-07-013): the entry inside is the
    CASE_MANAGER's, copied unchanged.
    """
    return announce_log_entry_activity(
        entry=ledger_entry_to_wire(entry),
        id_=hand_back_activity_id(receiving_actor_id, entry.id_),
        actor=case_manager_id,
        to=[receiving_actor_id],
    )


class InboxHandBackAdapter:
    """Queue a buffered ledger entry as a delivery to this actor's own inbox.

    Args:
        dl: The receiving actor's own DataLayer (ADR-0073), whose inbox queue
            the inbox loop drains.
        hold: Holds the Announce for the inbox replay the way the inbox holds
            a deferred delivery.  Injected by the inbox port factory, so this
            driven adapter does not import the driving inbox's staging.
    """

    def __init__(self, dl: DataLayer, hold: ActivityHolder) -> None:
        self._dl = dl
        self._hold = hold

    def hand_back_ledger_entry(
        self,
        entry: CaseLedgerEntry,
        case_manager_id: str,
        receiving_actor_id: str,
    ) -> None:
        """Wrap *entry* in an Announce from the CASE_MANAGER and queue it.

        Handing the same entry back twice names the same delivery
        (:func:`hand_back_activity_id`).  While the first is still held and
        queued, the second keeps the held copy and queues nothing; once
        replayed, a later hand-back finds the entry stored and is a no-op.  A
        held copy that is not queued (the append after an earlier hold
        failed) is queued now, so it is never stranded.  The Announce has no
        received body, because no peer sent it, so it is held as its row and
        replayed with no received evidence (VM-08-002).
        """
        announce = hand_back_announce(
            entry, case_manager_id, receiving_actor_id
        )
        self._hold(self._dl, announce)
        if announce.id_ in self._dl.inbox_list():
            logger.debug(
                "inbox hand-back: Announce(CaseLedgerEntry) '%s' is already"
                " queued for actor '%s'",
                announce.id_,
                receiving_actor_id,
            )
            return
        self._dl.inbox_append(announce.id_)
        logger.debug(
            "inbox hand-back: queued Announce(CaseLedgerEntry) '%s' for"
            " ledger entry '%s' (log_index=%d) from '%s' to actor '%s'",
            announce.id_,
            entry.id_,
            entry.log_index,
            case_manager_id,
            receiving_actor_id,
        )


__all__ = [
    "ActivityHolder",
    "InboxHandBackAdapter",
    "hand_back_activity_id",
    "hand_back_announce",
]
