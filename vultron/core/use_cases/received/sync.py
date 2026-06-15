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
"""Received use cases for SYNC-2/SYNC-3: accept or reject inbound log-entry
announcements, and handle hash-chain rejection replies.

Spec: SYNC-02-003, SYNC-03-001 through SYNC-03-003, SYNC-04-001, SYNC-04-002.
"""

import logging
from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.sync.announce_tree import (
    create_announce_log_entry_tree,
)
from vultron.core.behaviors.sync.reject_tree import (
    create_reject_log_entry_tree,
)
from vultron.core.models.events.sync import (
    AnnounceLogEntryReceivedEvent,
    RejectLogEntryReceivedEvent,
)
from vultron.core.models.pending_assertion import (
    PendingAssertionStore,
    get_pending_assertion_store,
)
from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.ports.case_persistence import (
    CasePersistence,
    CaseOutboxPersistence,
)
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.sync_helpers import _reconstruct_tail_hash  # noqa: F401

logger = logging.getLogger(__name__)


def _find_local_actor_id(dl: CasePersistence) -> str | None:
    """Find the local actor's ID from the DataLayer."""
    for actor_type in ("Service", "Person", "Organization"):
        actors = list(dl.list_objects(actor_type))
        if actors:
            return actors[0].id_
    return None


def _update_replication_state(
    case_id: str,
    peer_id: str,
    last_acknowledged_hash: str,
    dl: CasePersistence,
) -> None:
    """Upsert the :class:`VultronReplicationState` for *peer_id* in *case_id*.

    Creates a new record if none exists yet; updates the
    ``last_acknowledged_hash`` and ``updated_at`` fields on the existing one.

    Spec: SYNC-04-001, SYNC-04-002.
    """
    state = VultronReplicationState(
        case_id=case_id,
        peer_id=peer_id,
        last_acknowledged_hash=last_acknowledged_hash,
    )
    existing = dl.read(state.id_)
    if existing is not None:
        existing_state = cast(VultronReplicationState, existing)
        existing_state.last_acknowledged_hash = last_acknowledged_hash
        from vultron.core.models._helpers import _now_utc

        existing_state.updated_at = _now_utc()
        dl.save(existing_state)
        logger.debug(
            "sync: updated ReplicationState for peer '%s' in case '%s' "
            "→ last_acknowledged_hash=%.16s…",
            peer_id,
            case_id,
            last_acknowledged_hash,
        )
    else:
        dl.save(state)
        logger.debug(
            "sync: created ReplicationState for peer '%s' in case '%s' "
            "→ last_acknowledged_hash=%.16s…",
            peer_id,
            case_id,
            last_acknowledged_hash,
        )


class AnnounceLedgerEntryReceivedUseCase:
    """Process a received ``Announce(CaseLedgerEntry)`` activity.

    Validates the incoming entry against the local hash-chain tail and
    persists it if the chain is consistent.  On mismatch, sends a
    ``Reject(CaseLedgerEntry)`` back to the CaseActor carrying the local
    tail hash (SYNC-03-001).

    When *pending_assertions* is provided (or resolved from the per-actor
    registry), clears the matching pending assertion on receipt so that
    future commits for the same ``(case_id, event_type, log_object_id)``
    triple are no longer suppressed (SYNC-07-003).

    Spec: SYNC-02-003, SYNC-03-001 through SYNC-03-003, SYNC-07-003.
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AnnounceLogEntryReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        pending_assertions: PendingAssertionStore | None = None,
    ) -> None:
        self._dl = dl
        self._request = request
        self._sync_port = sync_port
        self._pending_assertions = pending_assertions

    def execute(self) -> None:
        request = self._request
        entry = request.log_entry
        if entry is None:
            logger.warning(
                "sync: received ANNOUNCE_CASE_LEDGER_ENTRY activity '%s' "
                "with no log entry object — ignoring",
                request.activity_id,
            )
            return

        logger.info(
            "sync: received log-entry announcement '%s' for case '%s' "
            "from actor '%s' (log_index=%d)",
            request.activity_id,
            entry.case_id,
            request.actor_id,
            entry.log_index,
        )
        result = BTBridge(datalayer=self._dl).execute_with_setup(
            tree=create_announce_log_entry_tree(),
            actor_id=request.receiving_actor_id or "unknown",
            activity=request,
            sync_port=self._sync_port,
        )
        if result.status == Status.FAILURE:
            logger.debug(
                "sync: announce BT returned FAILURE for '%s': %s",
                request.activity_id,
                result.feedback_message,
            )

        # Clear pending assertion for this entry regardless of BT outcome
        # (SYNC-07-003): both "recorded" and "rejected" dispositions confirm
        # the assertion has been processed by the log authority.
        receiving_actor_id = request.receiving_actor_id or ""
        store = self._pending_assertions
        if store is None and receiving_actor_id:
            store = get_pending_assertion_store(receiving_actor_id)
        if store is not None:
            store.clear(
                entry.case_id,
                entry.event_type,
                entry.log_object_id,
            )


class RejectLedgerEntryReceivedUseCase:
    """CaseActor handles a participant's rejection of a log entry announcement.

    When a participant rejects an ``Announce(CaseLedgerEntry)`` because the
    ``prev_log_hash`` does not match their local tail, the CaseActor:

    1. Updates :class:`~vultron.core.models.replication_state.VultronReplicationState`
       for the rejecting peer (SYNC-04-001, SYNC-04-002).
    2. Replays all missing entries from after the last-accepted hash to the
       peer (SYNC-03-002).

    When *pending_assertions* is provided (or resolved from the per-actor
    registry), clears the matching pending assertion on receipt so that
    future commits for the same ``(case_id, event_type, log_object_id)``
    triple are no longer suppressed (SYNC-07-004).

    Spec: SYNC-03-001, SYNC-03-002, SYNC-04-001, SYNC-04-002, SYNC-07-004.
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: RejectLogEntryReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        pending_assertions: PendingAssertionStore | None = None,
    ) -> None:
        self._dl = dl
        self._request = request
        self._sync_port = sync_port
        self._pending_assertions = pending_assertions

    def execute(self) -> None:
        request = self._request
        rejected_entry = request.rejected_entry
        if rejected_entry is None:
            logger.warning(
                "sync: received REJECT_CASE_LEDGER_ENTRY from '%s' "
                "with no log entry object — ignoring",
                request.actor_id,
            )
            return

        logger.info(
            "sync: received Reject(CaseLedgerEntry) from peer '%s' "
            "for case '%s', last_accepted_hash=%.16s…",
            request.actor_id,
            rejected_entry.case_id,
            request.last_accepted_hash,
        )
        result = BTBridge(datalayer=self._dl).execute_with_setup(
            tree=create_reject_log_entry_tree(),
            actor_id=request.receiving_actor_id or "unknown",
            activity=request,
            sync_port=self._sync_port,
        )
        if result.status == Status.FAILURE:
            logger.debug(
                "sync: reject BT returned FAILURE for '%s': %s",
                request.activity_id,
                result.feedback_message,
            )

        # Clear pending assertion so the rejected entry no longer suppresses
        # future commit attempts (SYNC-07-004 — no auto-retry, but operator
        # or catch-up gate can retry after clearing).
        receiving_actor_id = request.receiving_actor_id or ""
        store = self._pending_assertions
        if store is None and receiving_actor_id:
            store = get_pending_assertion_store(receiving_actor_id)
        if store is not None:
            store.clear(
                rejected_entry.case_id,
                rejected_entry.event_type,
                rejected_entry.log_object_id,
            )
