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

from vultron.core.models.case_log import GENESIS_HASH
from vultron.core.models.case_log_entry import VultronCaseLogEntry
from vultron.core.models.events.sync import (
    AnnounceLogEntryReceivedEvent,
    RejectLogEntryReceivedEvent,
)
from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.ports.case_persistence import (
    CasePersistence,
    CaseOutboxPersistence,
)

logger = logging.getLogger(__name__)


def _reconstruct_tail_hash(
    case_id: str, dl: CasePersistence
) -> tuple[str, int]:
    """Return the hash and index of the last accepted log entry for *case_id*.

    Queries all :class:`~vultron.core.models.case_log_entry.VultronCaseLogEntry`
    records for *case_id* and returns ``(tail_hash, tail_index)`` where
    ``tail_index`` is the highest ``log_index`` among recorded entries.

    Returns ``(GENESIS_HASH, -1)`` if no entries exist yet.
    """
    raw_entries: dict[str, dict] = dl.by_type("CaseLogEntry")
    entries: list[VultronCaseLogEntry] = []
    for data in raw_entries.values():
        if data.get("case_id") == case_id:
            try:
                entries.append(VultronCaseLogEntry.model_validate(data))
            except Exception:
                logger.debug(
                    "sync: skipping malformed CaseLogEntry record for case '%s'",
                    case_id,
                )

    if not entries:
        return GENESIS_HASH, -1

    entries.sort(key=lambda e: e.log_index)
    last = entries[-1]
    return last.entry_hash, last.log_index


def _find_local_actor_id(dl: CasePersistence) -> str | None:
    """Find the local actor's ID from the DataLayer.

    Looks for actor records (Service, Person, Organization) in the
    actor-scoped DataLayer.  Returns the first match, or ``None``.
    """
    for actor_type in ("Service", "Person", "Organization"):
        records = dl.by_type(actor_type)
        if records:
            return next(iter(records.keys()))
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


class AnnounceLogEntryReceivedUseCase:
    """Process a received ``Announce(CaseLogEntry)`` activity.

    Validates the incoming entry against the local hash-chain tail and
    persists it if the chain is consistent.  On mismatch, sends a
    ``Reject(CaseLogEntry)`` back to the CaseActor carrying the local
    tail hash (SYNC-03-001).

    Spec: SYNC-02-003, SYNC-03-001 through SYNC-03-003.
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AnnounceLogEntryReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request = request

    def execute(self) -> None:
        request = self._request
        entry = request.log_entry

        if entry is None:
            logger.warning(
                "sync: received ANNOUNCE_CASE_LOG_ENTRY activity '%s' "
                "with no log entry object — ignoring",
                request.activity_id,
            )
            return

        if not isinstance(entry, VultronCaseLogEntry):
            logger.warning(
                "sync: received ANNOUNCE_CASE_LOG_ENTRY activity '%s' "
                "with unexpected object type %s — ignoring",
                request.activity_id,
                type(entry).__name__,
            )
            return

        case_id: str = entry.case_id
        actor_id: str | None = request.actor_id

        logger.info(
            "sync: received log-entry announcement '%s' for case '%s' "
            "from actor '%s' (log_index=%d)",
            request.activity_id,
            case_id,
            actor_id,
            entry.log_index,
        )

        # Idempotency: skip if entry already stored
        existing = self._dl.read(entry.id_)
        if existing is not None:
            logger.debug(
                "sync: log entry '%s' already stored — skipping", entry.id_
            )
            return

        tail_hash, _tail_index = _reconstruct_tail_hash(case_id, self._dl)

        if entry.prev_log_hash != tail_hash:
            logger.warning(
                "sync: log-entry '%s' (log_index=%d) has prev_log_hash "
                "'%.16s…' but local tail is '%.16s…' — rejecting; "
                "sending Reject(CaseLogEntry) to sender (SYNC-03-001)",
                entry.id_,
                entry.log_index,
                entry.prev_log_hash,
                tail_hash,
            )
            self._send_rejection(entry, tail_hash, request.actor_id)
            return

        self._dl.save(entry)
        logger.info(
            "sync: accepted and stored log entry '%s' for case '%s' "
            "(log_index=%d, entry_hash=%.16s…)",
            entry.id_,
            case_id,
            entry.log_index,
            entry.entry_hash,
        )

    def _send_rejection(
        self,
        entry: VultronCaseLogEntry,
        tail_hash: str,
        case_actor_id: str,
    ) -> None:
        """Queue a :class:`RejectLogEntryActivity` back to the CaseActor.

        Spec: SYNC-03-001.
        """
        from vultron.wire.as2.vocab.activities.sync import (
            RejectLogEntryActivity,
        )
        from vultron.wire.as2.vocab.objects.case_log_entry import CaseLogEntry

        local_actor_id = _find_local_actor_id(self._dl) or "unknown"
        wire_entry = CaseLogEntry.from_core(entry)
        reject = RejectLogEntryActivity(
            actor=local_actor_id,
            object_=wire_entry,
            to=[case_actor_id],
            context=tail_hash,
        )
        self._dl.save(reject)
        self._dl.outbox_append(reject.id_)
        logger.info(
            "sync: sent Reject(CaseLogEntry) to '%s' "
            "with last_accepted_hash=%.16s…",
            case_actor_id,
            tail_hash,
        )


class RejectLogEntryReceivedUseCase:
    """CaseActor handles a participant's rejection of a log entry announcement.

    When a participant rejects an ``Announce(CaseLogEntry)`` because the
    ``prev_log_hash`` does not match their local tail, the CaseActor:

    1. Updates :class:`~vultron.core.models.replication_state.VultronReplicationState`
       for the rejecting peer (SYNC-04-001, SYNC-04-002).
    2. Replays all missing entries from after the last-accepted hash to the
       peer (SYNC-03-002).

    Spec: SYNC-03-001, SYNC-03-002, SYNC-04-001, SYNC-04-002.
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: RejectLogEntryReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request = request

    def execute(self) -> None:
        from vultron.core.use_cases.triggers.sync import (
            replay_missing_entries_trigger,
        )

        request = self._request
        peer_id = request.actor_id
        last_accepted_hash = request.last_accepted_hash

        rejected_entry = request.rejected_entry
        if rejected_entry is None:
            logger.warning(
                "sync: received REJECT_CASE_LOG_ENTRY from '%s' "
                "with no log entry object — ignoring",
                peer_id,
            )
            return

        case_id = rejected_entry.case_id

        logger.info(
            "sync: received Reject(CaseLogEntry) from peer '%s' "
            "for case '%s', last_accepted_hash=%.16s…",
            peer_id,
            case_id,
            last_accepted_hash,
        )

        # Update per-peer replication state (SYNC-04-001, SYNC-04-002)
        _update_replication_state(
            case_id=case_id,
            peer_id=peer_id,
            last_acknowledged_hash=last_accepted_hash,
            dl=self._dl,
        )

        # Find the CaseActor for this case to use as announce actor
        case_actor_id = self._find_case_actor(case_id)
        if case_actor_id is None:
            logger.warning(
                "sync: no CaseActor found for case '%s' — "
                "cannot replay entries to peer '%s'",
                case_id,
                peer_id,
            )
            return

        # Replay missing entries (SYNC-03-002)
        replayed = replay_missing_entries_trigger(
            case_id=case_id,
            peer_id=peer_id,
            from_hash=last_accepted_hash,
            case_actor_id=case_actor_id,
            dl=self._dl,
        )
        logger.info(
            "sync: replayed %d entries to peer '%s' for case '%s'",
            replayed,
            peer_id,
            case_id,
        )

    def _find_case_actor(self, case_id: str) -> str | None:
        """Locate the CaseActor (Service) associated with *case_id*.

        Searches ``Service``-type records in the DataLayer for one whose
        ``context`` equals *case_id* (same pattern as
        ``AddNoteToCaseReceivedUseCase._broadcast_note_to_participants``).
        """
        service_records = self._dl.by_type("Service")
        for obj_id, data in service_records.items():
            if data.get("context") == case_id:
                return obj_id
        # Fall back: return any Service actor if none has a matching context
        if service_records:
            return next(iter(service_records.keys()))
        return None
