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
from collections.abc import Callable
from dataclasses import dataclass

from vultron.adapters.driven.ledger_position_stamp import (
    with_sender_ledger_position,
)
from vultron.adapters.outbox_sealed_body import (
    read_sealed_body_dict,
    requeue_if_sealed,
    seal_outbound_body,
)
from vultron.core.models.activity_ids import derived_activity_id
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.sync_helpers import ledger_tail_position
from vultron.core.use_cases._helpers import add_activity_to_outbox
from vultron.wire.as2.factories import (
    announce_log_entry_activity,
    genesis_replay_reject_activity,
    read_ledger_position_activity,
    reject_log_entry_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Reject,
)
from vultron.wire.as2.vocab.objects.case_ledger_entry import (
    as_CaseLedgerEntry as WireCaseLedgerEntry,
)

logger = logging.getLogger(__name__)


def _body_ref_id(value: object) -> str | None:
    """The id of a reference in a sealed body: a bare string, or an object
    with ``id``."""
    if isinstance(value, str):
        return value or None
    ref = value.get("id") if isinstance(value, dict) else None
    return ref if isinstance(ref, str) and ref else None


@dataclass(frozen=True, slots=True)
class _QueuedRow:
    """What a queued row's sealed body says, as the pending index needs it.

    ``entry_id`` is ``None`` for every row that is not an
    ``Announce(CaseLedgerEntry)``.
    """

    entry_id: str | None
    recipients: frozenset[str]


_NOT_AN_ANNOUNCE = _QueuedRow(entry_id=None, recipients=frozenset())


def _read_queued_row(
    dl: CaseOutboxPersistence, activity_id: str
) -> _QueuedRow | None:
    """Read *activity_id*'s sealed body; ``None`` when it has none.

    The sealed body, not the activity record: it is what the outbox delivers
    (OX-07-001), so a row without one is never sent and is not pending.
    Reading the record instead rehydrated every queued activity, entry and
    payload included (#4906).  A row with no body is not remembered, so one
    sealed later is read then.
    """
    body = read_sealed_body_dict(dl, activity_id)
    if body is None:
        return None
    entry = body.get("object")
    if (
        body.get("type") != "Announce"
        or not isinstance(entry, dict)
        or entry.get("type") != "CaseLedgerEntry"
    ):
        return _NOT_AN_ANNOUNCE
    entry_id = _body_ref_id(entry)
    if not entry_id:
        return _NOT_AN_ANNOUNCE
    to = body.get("to") or []
    recipients = (
        _body_ref_id(r) for r in (to if isinstance(to, list) else [to])
    )
    return _QueuedRow(
        entry_id=entry_id,
        recipients=frozenset(r for r in recipients if r),
    )


def ledger_entry_to_wire(entry: CaseLedgerEntry) -> WireCaseLedgerEntry:
    """Convert a core log entry to the wire class an ``Announce`` carries."""
    return WireCaseLedgerEntry.model_validate(entry.model_dump(mode="json"))


class SyncActivityAdapter:
    """Adapter for :class:`~vultron.core.ports.sync_activity.SyncActivityPort`.

    Owns the full domain→wire→persist→outbox pipeline for sync activities.
    Core use cases pass domain objects and never touch wire types.
    """

    def __init__(self, dl: CaseOutboxPersistence) -> None:
        self._dl = dl
        self._pending_snapshot: tuple[str, ...] | None = None
        self._pending_index: dict[str, set[str]] = {}
        #: What each queued row's sealed body says, by activity id, for the
        #: rows read so far (``_pending_announce_index``).
        self._queued_rows: dict[str, _QueuedRow] = {}

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

    def send_reject_log_entry(
        self,
        entry: CaseLedgerEntry,
        tail_hash: str,
        actor_id: str,
        to: list[str],
    ) -> None:
        """Build and queue a ``Reject(CaseLedgerEntry)`` activity.

        The activity id is derived from the unapplied entry, the tail hash
        and the recipients, so a redelivery of the same mismatching entry
        builds no new activity and reuses the same id (ID-04-004).  If that
        Reject is sealed but no longer pending, it is queued once more under
        the same id and body, which the receiver deduplicates (ID-04-005).  A
        different tail hash is a different rejection and gets its own id.

        A backfill after a case copy (SYNC-16-007) names the chain's tail as
        both *entry* and *tail_hash*, so its id keys on the tail, not on the
        copy: the replay it asks for starts there whichever copy prompted
        it, and the entries committed after that replay reach the replica by
        fan-out.  The genesis-replay ``Reject`` has no entry to key on, so
        :meth:`send_genesis_replay_reject` keys on the copy's position.

        Spec: SYNC-03-001.
        """
        reject_id = derived_activity_id(
            "reject-log-entry", actor_id, entry.id_, tail_hash, *sorted(to)
        )
        self._queue_reject(
            reject_id,
            actor_id,
            f"Reject(CaseLedgerEntry) for entry '{entry.id_}'",
            lambda: reject_log_entry_activity(
                entry=ledger_entry_to_wire(entry),
                actor=actor_id,
                to=to,
                id_=reject_id,
            ),
        )

    def send_genesis_replay_reject(
        self,
        case_id: str,
        copy_tail_hash: str,
        actor_id: str,
        to: list[str],
    ) -> None:
        """Build and queue the ``Reject(CaseLedgerEntry)`` that names no entry.

        The activity id is derived from the case, the ledger position of the
        copy that replaced it and the recipients, so a repeat for the same copy builds
        no new activity and reuses the id (ID-04-004), while a request after
        a later copy is its own; a sealed one no longer pending is queued
        once more (ID-04-005).

        Spec: SYNC-16-007.
        """
        reject_id = derived_activity_id(
            "genesis-replay-reject",
            actor_id,
            case_id,
            copy_tail_hash,
            *sorted(to),
        )
        self._queue_reject(
            reject_id,
            actor_id,
            f"genesis-replay Reject(CaseLedgerEntry) for case '{case_id}'",
            lambda: genesis_replay_reject_activity(
                case_id,
                ledger_tail_position(case_id, self._dl),
                actor=actor_id,
                to=to,
                id_=reject_id,
            ),
        )

    def send_read_ledger_entry(
        self,
        case_id: str,
        ledger_position: LedgerPosition,
        actor_id: str,
        to: list[str],
    ) -> None:
        """Build and queue a ``Read(CaseLedgerEntry)`` position statement.

        The activity gets a fresh id: each statement is a new observation of
        the participant's position, and the CASE_MANAGER must answer it even
        when an earlier one named the same entry, because its ledger may have
        grown since (SYNC-17-004).  A derived id would make the repeat a
        redelivery the CASE_MANAGER skips.

        Spec: SYNC-17-001, SYNC-17-008.
        """
        read = read_ledger_position_activity(
            case_id, ledger_position, actor=actor_id, to=to
        )
        self._dl.save(read)
        seal_outbound_body(self._dl, read)
        add_activity_to_outbox(actor_id, read.id_, self._dl)
        logger.info(
            "sync adapter: queued Read(CaseLedgerEntry) '%s' for entry '%s'"
            " to %s",
            read.id_,
            read.object_,
            to,
        )

    def _queue_reject(
        self,
        reject_id: str,
        actor_id: str,
        label: str,
        build: Callable[[], as_Reject],
    ) -> None:
        """Build, store, seal and queue a Reject, unless it is already built.

        A Reject already sealed under *reject_id* is re-queued instead, with
        the same id and body, which the receiver deduplicates (ID-04-005).
        """
        if requeue_if_sealed(self._dl, reject_id):
            logger.info(
                "sync adapter: %s '%s' was already built; not building it"
                " again",
                label,
                reject_id,
            )
            return
        # The sender's tail, when it holds the case (SYNC-18-001): a peer that
        # holds no case yet states none, and the CASE_MANAGER replays it from
        # genesis (SYNC-15-015).
        reject = with_sender_ledger_position(self._dl, build())
        self._dl.save(reject)
        seal_outbound_body(self._dl, reject)
        # ``self._dl`` selects the queue; *actor_id* is passed for the log label
        # only (see ``add_activity_to_outbox``).  It no longer guards against a
        # shared or differently-scoped DataLayer — there is no unscoped store to
        # guard against under ADR-0073 — and it must not be read as doing so.
        add_activity_to_outbox(actor_id, reject.id_, self._dl)
        logger.info(
            "sync adapter: queued %s '%s' → %s", label, reject.id_, reject.to
        )

    def _pending_announce_index(self) -> dict[str, set[str]]:
        """``entry id → recipients`` for every ``Announce`` still queued here.

        A Reject that reaches the CASE_MANAGER after the peer's gap has already
        drained still names an advanced position, so SYNC-15-010 makes it
        replay; without this index every such Reject re-queued a suffix the
        outbox already held for that peer — ten late Rejects put 116 duplicate
        rows ahead of the next entry's fan-out to every other peer (#3602).
        The outbox is this adapter's own store (ADR-0073), and reading a queued
        activity's sealed body back is the adapter's to do (DL-06-004), not
        core's (DL-06-001).

        The index is rebuilt only when the queue's id list changes: a replay
        asks once per entry, and reading every row per entry would be
        O(queue × suffix) reads under the store's session guard.  A rebuild
        reads only the rows this adapter has not read yet: every send queues a
        row, so re-reading the whole queue on each one made a fan-out of *n*
        Announces cost O(n × queue) reads (#4906).  A row's sealed body is
        write-once (``seal_outbound_body``), so what was read for it stands.
        """
        snapshot = tuple(self._dl.outbox_list())
        if snapshot == self._pending_snapshot:
            return self._pending_index
        rows: dict[str, _QueuedRow] = {}
        for activity_id in snapshot:
            row = self._queued_rows.get(activity_id)
            if row is None:
                row = _read_queued_row(self._dl, activity_id)
            if row is not None:
                rows[activity_id] = row
        index: dict[str, set[str]] = {}
        for row in rows.values():
            if row.entry_id is not None:
                index.setdefault(row.entry_id, set()).update(row.recipients)
        # Only the rows still queued are kept, so the memo is bounded by the
        # queue rather than by the adapter's lifetime.
        self._queued_rows = rows
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
        wire_entry = ledger_entry_to_wire(entry)
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
