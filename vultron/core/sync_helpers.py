#!/usr/bin/env python
"""Shared helpers for SYNC log-replication workflows."""

from typing import Any

from vultron.core.models.case_ledger import GENESIS_HASH
from vultron.core.models.protocols import LogEntryModel, is_log_entry_model
from vultron.core.ports.case_persistence import CasePersistence


def _reconstruct_tail_hash(
    case_id: str, dl: CasePersistence
) -> tuple[str, int]:
    """Return the hash and index of the last accepted log entry for *case_id*."""
    entries: list[LogEntryModel] = [
        obj
        for obj in dl.list_objects("CaseLedgerEntry")
        if is_log_entry_model(obj) and obj.case_id == case_id
    ]

    if not entries:
        return GENESIS_HASH, -1

    entries.sort(key=lambda entry: entry.log_index)
    last = entries[-1]
    return last.entry_hash, last.log_index


def _find_equivalent_recorded_entry(
    *,
    case_id: str,
    object_id: str,
    event_type: str,
    payload_snapshot: dict[str, Any],
    dl: CasePersistence,
) -> LogEntryModel | None:
    """Return an already-recorded canonical entry with equivalent semantics.

    "Equivalent" means same case, object, event type, and payload snapshot.
    This supports idempotent handling of participant retries without appending
    duplicate canonical entries for the same logical assertion.
    """
    matches: list[LogEntryModel] = [
        entry
        for obj in dl.list_objects("CaseLedgerEntry")
        if is_log_entry_model(obj)
        for entry in [obj]
        if entry.case_id == case_id
        and entry.disposition == "recorded"
        and entry.log_object_id == object_id
        and entry.event_type == event_type
        and entry.payload_snapshot == payload_snapshot
    ]
    if not matches:
        return None
    matches.sort(key=lambda entry: entry.log_index)
    return matches[-1]
