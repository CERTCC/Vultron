#!/usr/bin/env python
"""Shared helpers for SYNC log-replication workflows."""

from typing import Any

from vultron.core.models.case_ledger import GENESIS_HASH
from vultron.core.models.protocols import LogEntryModel, is_log_entry_model
from vultron.core.ports.case_persistence import CasePersistence


def is_ledger_fresh_for_case(
    case_id: str, dl: CasePersistence
) -> tuple[bool, str]:
    """Check whether the local ledger for *case_id* is contiguous from genesis.

    Returns ``(True, "")`` when the actor's local log entries form an
    unbroken, hash-verified sequence starting at ``log_index=0`` with
    ``prev_log_hash == GENESIS_HASH``.  Returns ``(False, reason)`` if any
    index gap or hash mismatch is found.

    An empty local log (no entries yet) is considered trivially fresh: the
    actor's acknowledged prefix is the empty prefix, which is contiguous.
    This satisfies SYNC-10-005 — the gate MUST NOT require the actor's tip to
    equal the CaseActor's current tip.

    Spec: SYNC-10-003, SYNC-10-004, SYNC-10-005.

    Args:
        case_id: URI of the case whose local ledger to check.
        dl: The actor-local DataLayer to query.

    Returns:
        A 2-tuple ``(is_fresh, reason)``.  ``reason`` is an empty string when
        fresh; a human-readable explanation when stale.
    """
    entries: list[LogEntryModel] = [
        obj
        for obj in dl.list_objects("CaseLedgerEntry")
        if is_log_entry_model(obj) and obj.case_id == case_id
    ]

    if not entries:
        return True, ""

    entries.sort(key=lambda entry: entry.log_index)

    first = entries[0]
    if first.log_index != 0:
        return False, (
            f"genesis entry missing: first local entry has "
            f"log_index={first.log_index} (expected 0)"
        )
    if first.prev_log_hash != GENESIS_HASH:
        return False, (
            f"genesis entry prev_log_hash mismatch: "
            f"got {first.prev_log_hash!r}, want GENESIS_HASH"
        )

    for i in range(1, len(entries)):
        prev = entries[i - 1]
        curr = entries[i]
        if curr.log_index != prev.log_index + 1:
            return False, (
                f"log gap: entries jump from index {prev.log_index} "
                f"to {curr.log_index}"
            )
        if curr.prev_log_hash != prev.entry_hash:
            return False, (
                f"hash mismatch at index {curr.log_index}: "
                f"prev_log_hash={curr.prev_log_hash!r} != "
                f"preceding entry_hash={prev.entry_hash!r}"
            )

    return True, ""


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
