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

"""Adapter implementing :class:`~vultron.core.ports.sync_activity.SyncActivityPort`.

Converts :class:`~vultron.core.models.case_ledger_entry.CaseLedgerEntry`
objects to wire-layer
:class:`~vultron.wire.as2.vocab.objects.case_ledger_entry.CaseLedgerEntry`
objects, builds the appropriate AS2 activity via factory functions, persists
the activity, and queues it to the actor's outbox for delivery.

This adapter is the **sole** location where sync-related domain→wire
translation occurs, keeping ``vultron/core/`` free of wire-layer imports
(ARCH-01-001).

See also:
    - ``vultron/core/ports/sync_activity.py`` — port Protocol
    - ``vultron/wire/as2/factories/sync.py`` — factory functions
    - ``vultron/wire/as2/factories/AGENTS.md``
"""

import logging

from vultron.adapters.outbox_sealed_body import seal_outbound_body
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.use_cases._helpers import add_activity_to_outbox
from vultron.wire.as2.factories import (
    announce_log_entry_activity,
    reject_log_entry_activity,
)
from vultron.wire.as2.vocab.objects.case_ledger_entry import (
    as_CaseLedgerEntry as WireCaseLedgerEntry,
)

logger = logging.getLogger(__name__)


def _ref_id(value: object) -> str | None:
    """The id of a stored reference: a bare string, or an object with ``id_``."""
    if isinstance(value, str):
        return value or None
    ref = getattr(value, "id_", None)
    return ref if isinstance(ref, str) and ref else None


class SyncActivityAdapter:
    """Adapter for :class:`~vultron.core.ports.sync_activity.SyncActivityPort`.

    Owns the full domain→wire→persist→outbox pipeline for sync activities.
    Core use cases pass domain objects and never touch wire types.
    """

    def __init__(self, dl: CaseOutboxPersistence) -> None:
        self._dl = dl
        self._pending_snapshot: tuple[str, ...] | None = None
        self._pending_index: dict[str, set[str]] = {}

    def for_store(self, dl: CaseOutboxPersistence) -> "SyncActivityAdapter":
        """Return an equivalent adapter that reads and writes *dl* (DL-07-009).

        Opting into
        :func:`~vultron.core.behaviors.store_scope.port_for_store`, for the same
        reason as ``TriggerActivityAdapter.for_store``: this adapter both saves
        the activity and appends it to an outbox, so a BT executing as an actor
        other than the one this adapter was built for would split those two writes
        across two stores (ISSUE-2548).
        """
        if dl is self._dl:
            return self
        return type(self)(dl)

    def _to_wire(self, entry: CaseLedgerEntry) -> WireCaseLedgerEntry:
        """Convert a log entry to its wire-layer representation."""
        return WireCaseLedgerEntry.model_validate(
            entry.model_dump(mode="json")
        )

    def send_reject_log_entry(
        self,
        entry: CaseLedgerEntry,
        tail_hash: str,
        actor_id: str,
        to: list[str],
    ) -> None:
        """Build and queue a ``Reject(CaseLedgerEntry)`` activity.

        Spec: SYNC-03-001.
        """
        wire_entry = self._to_wire(entry)
        reject = reject_log_entry_activity(
            entry=wire_entry,
            context=tail_hash,
            actor=actor_id,
            to=to,
        )
        self._dl.save(reject)
        seal_outbound_body(self._dl, reject)
        # ``self._dl`` selects the queue; *actor_id* is passed for the log label
        # only (see ``add_activity_to_outbox``).  It no longer guards against a
        # shared or differently-scoped DataLayer — there is no unscoped store to
        # guard against under ADR-0073 — and it must not be read as doing so.
        add_activity_to_outbox(actor_id, reject.id_, self._dl)
        logger.info(
            "sync adapter: queued Reject(CaseLedgerEntry) '%s' → %s",
            reject.id_,
            to,
        )

    def _pending_announce_index(self) -> dict[str, set[str]]:
        """``entry id → recipients`` for every ``Announce`` still queued here.

        A Reject that reaches the CASE_MANAGER after the peer's gap has already
        drained still names an advanced position, so SYNC-15-010 makes it
        replay; without this index every such Reject re-queued a suffix the
        outbox already held for that peer — ten late Rejects put 116 duplicate
        rows ahead of the next entry's fan-out to every other peer (#3602).
        The outbox is this adapter's own store (ADR-0073), and reading a queued
        activity's envelope back is the adapter's to do (DL-06-004), not core's
        (DL-06-001).

        The index is rebuilt only when the queue's id list changes: a replay
        asks once per entry, and reading every row per entry would be
        O(queue × suffix) reads under the store's session guard.
        """
        snapshot = tuple(self._dl.outbox_list())
        if snapshot == self._pending_snapshot:
            return self._pending_index
        index: dict[str, set[str]] = {}
        for activity_id in snapshot:
            activity = self._dl.read(activity_id)
            if getattr(activity, "type_", None) != "Announce":
                continue
            entry = getattr(activity, "object_", None)
            if getattr(entry, "type_", None) != "CaseLedgerEntry":
                continue
            entry_id = _ref_id(entry)
            if not entry_id:
                continue
            recipients = index.setdefault(entry_id, set())
            for recipient in getattr(activity, "to", None) or []:
                recipient_id = _ref_id(recipient)
                if recipient_id:
                    recipients.add(recipient_id)
        self._pending_snapshot = snapshot
        self._pending_index = index
        return index

    def send_announce_log_entry(
        self,
        entry: CaseLedgerEntry,
        actor_id: str,
        to: list[str],
    ) -> bool:
        """Build and queue an ``Announce(CaseLedgerEntry)`` activity.

        Uses actor-aware outbox queueing via
        :func:`~vultron.core.use_cases._helpers.add_activity_to_outbox`.

        Returns ``False`` without queueing when an ``Announce`` of *entry* to
        every recipient in *to* is already pending in this outbox
        (SYNC-15-012); ``True`` when a row was queued.

        Spec: SYNC-02-002, SYNC-03-002, SYNC-15-012.
        """
        pending = self._pending_announce_index().get(entry.id_, set())
        if to and all(recipient in pending for recipient in to):
            logger.debug(
                "sync adapter: Announce(CaseLedgerEntry) '%s' → %s already"
                " pending in outbox; not queued again (SYNC-15-012)",
                entry.id_,
                to,
            )
            return False
        wire_entry = self._to_wire(entry)
        announce = announce_log_entry_activity(
            entry=wire_entry,
            actor=actor_id,
            to=to,
        )
        self._dl.save(announce)
        seal_outbound_body(self._dl, announce)
        add_activity_to_outbox(actor_id, announce.id_, self._dl)
        logger.debug(
            "sync adapter: queued Announce(CaseLedgerEntry) '%s' → %s",
            announce.id_,
            to,
        )
        return True
