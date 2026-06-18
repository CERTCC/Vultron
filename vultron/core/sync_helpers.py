#!/usr/bin/env python
"""Shared helpers for SYNC log-replication workflows."""

from typing import Any

from vultron.core.models.protocols import LogEntryModel, is_log_entry_model
from vultron.core.ports.case_persistence import CasePersistence


def _get_case_genesis_hash(case_id: str, dl: CasePersistence) -> str:
    """Return the per-case genesis hash for *case_id* from the DataLayer.

    Looks up the :class:`~vultron.core.models.case.VulnerabilityCase` in *dl*
    and returns its ``genesis_hash`` field.  Returns ``""`` when the case is
    not found or has no genesis hash (callers should treat ``""`` as "genesis
    hash unknown — skip genesis-hash validation").

    Args:
        case_id: URI of the :class:`~vultron.core.models.case.VulnerabilityCase`.
        dl: DataLayer to query.

    Returns:
        64-character hex SHA-256 genesis hash, or ``""`` if unavailable.
    """
    from vultron.core.models.case import VulnerabilityCase

    case_obj = dl.read(case_id)
    if isinstance(case_obj, VulnerabilityCase):
        if case_obj.genesis_hash:
            return case_obj.genesis_hash
    # Duck-type fallback: wire-layer VulnerabilityCase also has genesis_hash
    genesis = getattr(case_obj, "genesis_hash", "")
    if genesis and isinstance(genesis, str):
        return genesis
    return ""


def is_ledger_fresh_for_case(
    case_id: str,
    dl: CasePersistence,
    genesis_hash: str | None = None,
) -> tuple[bool, str]:
    """Check whether the local ledger for *case_id* is contiguous from genesis.

    Returns ``(True, "")`` when the actor's local log entries form an
    unbroken, hash-verified sequence starting at ``log_index=0`` with
    ``prev_log_hash`` equal to the per-case genesis hash.  Returns
    ``(False, reason)`` if any index gap or hash mismatch is found.

    An empty local log (no entries yet) is considered trivially fresh: the
    actor's acknowledged prefix is the empty prefix, which is contiguous.
    This satisfies SYNC-10-005 — the gate MUST NOT require the actor's tip to
    equal the CaseActor's current tip.

    When *genesis_hash* is ``None``, it is looked up from the DataLayer via
    :func:`_get_case_genesis_hash`.  When the genesis hash cannot be
    determined (``None`` lookup returns ``""`` and no explicit value is
    provided), the genesis-entry ``prev_log_hash`` check is skipped.

    Spec: SYNC-10-003, SYNC-10-004, SYNC-10-005, CLP-08-004.

    Args:
        case_id: URI of the case whose local ledger to check.
        dl: The actor-local DataLayer to query.
        genesis_hash: Expected ``prev_log_hash`` of the first entry.  When
            ``None`` (default), looked up automatically from *dl*.  Pass ``""``
            to explicitly skip the genesis-entry check.

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

    effective_genesis = (
        genesis_hash
        if genesis_hash is not None
        else _get_case_genesis_hash(case_id, dl)
    )
    if effective_genesis and first.prev_log_hash != effective_genesis:
        return False, (
            f"genesis entry prev_log_hash mismatch: "
            f"got {first.prev_log_hash!r}, "
            f"want per-case genesis hash {effective_genesis[:16]!r}…"
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
    """Return the hash and index of the last accepted log entry for *case_id*.

    When no entries are stored locally for *case_id*, returns the per-case
    genesis hash (looked up from the DataLayer) and index ``-1``.  If the
    case's genesis hash is not available, returns ``""`` and ``-1``.

    Spec: CLP-08-005.

    Args:
        case_id: URI of the parent :class:`VulnerabilityCase`.
        dl: DataLayer to query.

    Returns:
        A 2-tuple ``(tail_hash, tail_index)``.
    """
    entries: list[LogEntryModel] = [
        obj
        for obj in dl.list_objects("CaseLedgerEntry")
        if is_log_entry_model(obj) and obj.case_id == case_id
    ]

    if not entries:
        return _get_case_genesis_hash(case_id, dl), -1

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
