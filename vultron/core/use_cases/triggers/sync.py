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
"""Trigger helpers for SYNC-2/SYNC-3: commit a log entry and fan it out to
peers; replay missing entries on hash-chain rejection.

Public entry points:
- :func:`commit_log_entry_trigger`
- :func:`replay_missing_entries_trigger`

Spec: SYNC-02-002, SYNC-02-003, SYNC-03-001, SYNC-03-002.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import VultronCaseLedgerEntry
from vultron.core.models.protocols import (
    LogEntryModel,
    is_case_model,
    is_log_entry_model,
)
from vultron.core.ports.case_persistence import (
    CaseOutboxPersistence,
)
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.sync_helpers import (
    _find_equivalent_recorded_entry,
    _reconstruct_tail_hash,
)
from vultron.core.use_cases._helpers import case_addressees
from vultron.core.use_cases._helpers import build_activity_payload_snapshot
from vultron.errors import VultronError

if TYPE_CHECKING:
    from vultron.core.models.events.base import VultronEvent

logger = logging.getLogger(__name__)


def extract_activity_snapshot(
    request: "VultronEvent", dl: CaseOutboxPersistence | None = None
) -> dict[str, Any]:
    """Return a normalised AS2 payload snapshot from a ``VultronEvent``.

    When ``request.activity`` is populated (``include_activity=True`` in
    the registry entry), returns its ``model_dump`` as the snapshot so
    that case-ledger entries carry the full inbound AS2 activity object.
    Returns an empty dict when no activity snapshot is available.

    Args:
        request: The inbound domain event produced by ``extract_intent()``.
        dl: Optional DataLayer used to inline known nested object-reference
            fields from storage.

    Returns:
        A JSON-serialisable dict suitable for ``payload_snapshot``.

    Spec: SYNC-02-002, SYNC-02-003.
    """
    return cast(
        dict[str, Any],
        build_activity_payload_snapshot(request.activity, dl=dl),
    )


def _to_persistable_entry(
    chain_entry: HashChainLedgerRecord,
) -> VultronCaseLedgerEntry:
    """Convert a hash-chained :class:`HashChainLedgerRecord` to a :class:`VultronCaseLedgerEntry`.

    Copies all fields so that the entry can be stored via the DataLayer.
    """
    return VultronCaseLedgerEntry(
        case_id=chain_entry.case_id,
        log_index=chain_entry.log_index,
        disposition=chain_entry.disposition,
        term=chain_entry.term,
        log_object_id=chain_entry.object_id,
        event_type=chain_entry.event_type,
        payload_snapshot=dict(chain_entry.payload_snapshot),
        prev_log_hash=chain_entry.prev_log_hash,
        entry_hash=chain_entry.entry_hash,
        reason_code=chain_entry.reason_code,
        reason_detail=chain_entry.reason_detail,
    )


def _as_persistable_log_entry(entry: LogEntryModel) -> VultronCaseLedgerEntry:
    if isinstance(entry, VultronCaseLedgerEntry):
        return entry
    return VultronCaseLedgerEntry.model_validate(entry.model_dump(mode="json"))


def _fan_out_log_entry(
    case_id: str,
    entry: VultronCaseLedgerEntry,
    actor_id: str,
    dl: CaseOutboxPersistence,
    sync_port: SyncActivityPort | None = None,
) -> None:
    """Create one ``Announce(CaseLedgerEntry)`` per peer and queue for delivery.

    Reads the case from the DataLayer to get the participant list.
    Participants other than *actor_id* (the CaseActor) each receive their
    own outbox activity.

    Spec: SYNC-02-002.
    """
    if sync_port is None:
        logger.debug(
            "sync fan-out: sync_port not injected — "
            "skipping fan-out for log entry '%s' in case '%s'",
            entry.id_,
            case_id,
        )
        return

    case_obj = dl.read(case_id)
    if not is_case_model(case_obj):
        logger.warning(
            "sync fan-out: case '%s' not found or not a VulnerabilityCase — "
            "skipping fan-out for log entry '%s'",
            case_id,
            entry.id_,
        )
        return

    recipients = case_addressees(case_obj, excluding_actor_id=actor_id)
    if not recipients:
        logger.debug(
            "sync fan-out: no other participants for case '%s' — "
            "log entry '%s' not forwarded",
            case_id,
            entry.id_,
        )
        return

    for recipient_id in recipients:
        sync_port.send_announce_log_entry(
            entry=entry,
            actor_id=actor_id,
            to=[recipient_id],
        )
        logger.info(
            "sync fan-out: queued Announce(CaseLedgerEntry) → '%s'",
            recipient_id,
        )


def commit_log_entry_trigger(
    case_id: str,
    object_id: str,
    event_type: str,
    actor_id: str,
    dl: CaseOutboxPersistence,
    payload_snapshot: dict[str, Any] | None = None,
    term: int | None = None,
    reason_code: str | None = None,
    reason_detail: str | None = None,
    disposition: str = "recorded",
    sync_port: SyncActivityPort | None = None,
) -> VultronCaseLedgerEntry:
    """Commit a new log entry to the local chain and fan it out to peers.

    Reconstructs the current chain tail from the DataLayer, appends the new
    entry via :class:`~vultron.core.models.case_ledger.CaseLedger`, converts
    to a :class:`~vultron.core.models.case_ledger_entry.VultronCaseLedgerEntry`,
    persists it, and fans it out to all case participants via
    ``Announce(CaseLedgerEntry)`` activities.

    Args:
        case_id: URI of the parent :class:`VulnerabilityCase`.
        object_id: URI of the asserted activity or primary object.
        event_type: Short machine-readable event descriptor.
        actor_id: URI of the CaseActor performing the commit.
        dl: CaseOutboxPersistence instance for persistence and outbox access.
        payload_snapshot: Optional normalised payload snapshot.
        term: Optional Raft cluster term (single-node → ``None``).
        reason_code: Required when *disposition* is ``"rejected"``.
        reason_detail: Optional human-readable rejection detail.
        disposition: ``"recorded"`` (default) or ``"rejected"``.
        sync_port: Optional port for fan-out via ``Announce(CaseLedgerEntry)``.

    Returns:
        The newly created (or existing) :class:`VultronCaseLedgerEntry`.

    Spec: SYNC-02-002, SYNC-02-003, SYNC-03-001.
    """
    normalized_snapshot = payload_snapshot or {}
    existing = _find_equivalent_recorded_entry(
        case_id=case_id,
        object_id=object_id,
        event_type=event_type,
        payload_snapshot=normalized_snapshot,
        dl=dl,
    )
    if existing is not None:
        existing_entry = _as_persistable_log_entry(existing)
        logger.info(
            "sync: idempotent commit hit for case '%s' event_type=%s "
            "object_id='%s' (reusing log_index=%d)",
            case_id,
            event_type,
            object_id,
            existing_entry.log_index,
        )
        _fan_out_log_entry(
            case_id, existing_entry, actor_id, dl, sync_port=sync_port
        )
        return existing_entry

    tail_hash, tail_index = _reconstruct_tail_hash(case_id, dl)

    # Create the new entry directly using HashChainLedgerRecord so the entry_hash is
    # auto-computed by the model_validator.  We do not use CaseLedger.append()
    # here because that always starts a fresh log at index 0; we carry forward
    # the DataLayer state via tail_hash and tail_index instead.
    chain_entry = HashChainLedgerRecord(
        case_id=case_id,
        log_index=tail_index + 1,
        object_id=object_id,
        event_type=event_type,
        disposition=disposition,  # type: ignore[arg-type]
        payload_snapshot=normalized_snapshot,
        prev_log_hash=tail_hash,
        term=term,
        reason_code=reason_code,
        reason_detail=reason_detail,
    )

    entry = _to_persistable_entry(chain_entry)
    dl.save(entry)

    logger.info(
        "sync: committed log entry '%s' for case '%s' "
        "(log_index=%d, event_type=%s)",
        entry.id_,
        case_id,
        entry.log_index,
        event_type,
    )

    _fan_out_log_entry(case_id, entry, actor_id, dl, sync_port=sync_port)

    return entry


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

    When *from_hash* is ``GENESIS_HASH`` (or not found among stored entries),
    ALL entries for the case are replayed.

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
    # If not found (e.g. GENESIS_HASH or unknown), start from index -1 so
    # all entries are replayed.
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
