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
"""Received use case for SYNC-2: accept or reject inbound log-entry announcements.

Spec: SYNC-02-003, SYNC-03-001, SYNC-03-002, SYNC-03-003.
"""

import logging

from vultron.core.models.case_log import GENESIS_HASH
from vultron.core.models.case_log_entry import VultronCaseLogEntry
from vultron.core.models.events.sync import AnnounceLogEntryReceivedEvent
from vultron.core.ports.datalayer import DataLayer

logger = logging.getLogger(__name__)


def _reconstruct_tail_hash(case_id: str, dl: DataLayer) -> tuple[str, int]:
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


class AnnounceLogEntryReceivedUseCase:
    """Process a received ``Announce(CaseLogEntry)`` activity.

    Validates the incoming entry against the local hash-chain tail and
    persists it if the chain is consistent.  On mismatch, logs a warning
    and discards the entry so the sender can be notified via the trigger
    layer.

    Spec: SYNC-02-003, SYNC-03-001 through SYNC-03-003.
    """

    def __init__(
        self,
        dl: DataLayer,
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
                "'%.16s…' but local tail is '%.16s…' — discarding; "
                "sender may need to resync",
                entry.id_,
                entry.log_index,
                entry.prev_log_hash,
                tail_hash,
            )
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
