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
"""Trigger helper for SYNC-3: replay missing log entries on hash-chain rejection.

Public entry point:

- :func:`replay_missing_entries_trigger`

Spec: SYNC-03-001, SYNC-03-002.

Note: ``commit_log_entry_trigger`` was removed (BT-06-006).  All ledger
commits now go through :class:`~vultron.core.behaviors.case.nodes.lifecycle.CommitCaseLedgerEntryNode`
via ``BTBridge.execute_with_setup()``.
"""

from __future__ import annotations

import logging

from vultron.core.models.protocols import (
    LogEntryModel,
    is_log_entry_model,
)
from vultron.core.ports.case_persistence import (
    CaseOutboxPersistence,
)
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.errors import VultronError

logger = logging.getLogger(__name__)


def replay_missing_entries_trigger(
    case_id: str,
    peer_id: str,
    from_hash: str,
    case_actor_id: str,
    dl: CaseOutboxPersistence,
    sync_port: SyncActivityPort | None = None,
) -> int:
    """Replay all log entries after *from_hash* to a specific peer.

    Queries all :class:`~vultron.core.models.case_ledger_entry.VultronCaseLedgerEntry`
    records for *case_id*, finds entries with ``log_index`` strictly greater
    than the index of the entry whose ``entry_hash`` matches *from_hash*,
    and queues an ``Announce(CaseLedgerEntry)`` activity for each to *peer_id*.

    When *from_hash* is ``""`` (empty string, indicating no entry acknowledged)
    or is not found among stored entries, ALL entries for the case are replayed.

    Args:
        case_id: URI of the parent :class:`VulnerabilityCase`.
        peer_id: URI of the participant who needs the missing entries.
        from_hash: ``entry_hash`` of the last entry acknowledged by *peer_id*.
        case_actor_id: URI of the CaseActor sending the announcements.
        dl: CaseOutboxPersistence instance for persistence and outbox access.

    Returns:
        The number of entries replayed (i.e. queued for delivery).

    Spec: SYNC-03-002.
    """
    entries: list[LogEntryModel] = [
        obj
        for obj in dl.list_objects("CaseLedgerEntry")
        if is_log_entry_model(obj) and obj.case_id == case_id
    ]

    if not entries:
        logger.debug(
            "sync replay: no entries for case '%s' — nothing to replay",
            case_id,
        )
        return 0

    entries.sort(key=lambda e: e.log_index)

    # Find the log_index of the entry matching from_hash.
    # If not found (e.g. "" empty string or unknown hash), start from index -1
    # so all entries are replayed.
    from_index = -1
    for entry in entries:
        if entry.entry_hash == from_hash:
            from_index = entry.log_index
            break

    missing = [e for e in entries if e.log_index > from_index]
    if not missing:
        logger.debug(
            "sync replay: peer '%s' is already up-to-date for case '%s'",
            peer_id,
            case_id,
        )
        return 0

    if sync_port is None:
        raise VultronError(
            "replay_missing_entries_trigger: sync_port must be injected — "
            "no adapter fallback is available in the core layer."
        )

    replayed = 0
    for entry in missing:
        sync_port.send_announce_log_entry(
            entry=entry,
            actor_id=case_actor_id,
            to=[peer_id],
        )
        logger.info(
            "sync replay: queued Announce(CaseLedgerEntry) "
            "(log_index=%d) → '%s'",
            entry.log_index,
            peer_id,
        )
        replayed += 1

    return replayed
