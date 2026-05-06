#!/usr/bin/env python
"""Shared helpers for SYNC log-replication workflows."""

from vultron.core.models.case_log import GENESIS_HASH
from vultron.core.models.protocols import LogEntryModel, is_log_entry_model
from vultron.core.ports.case_persistence import CasePersistence


def _reconstruct_tail_hash(
    case_id: str, dl: CasePersistence
) -> tuple[str, int]:
    """Return the hash and index of the last accepted log entry for *case_id*."""
    entries: list[LogEntryModel] = [
        obj
        for obj in dl.list_objects("CaseLogEntry")
        if is_log_entry_model(obj) and obj.case_id == case_id
    ]

    if not entries:
        return GENESIS_HASH, -1

    entries.sort(key=lambda entry: entry.log_index)
    last = entries[-1]
    return last.entry_hash, last.log_index
