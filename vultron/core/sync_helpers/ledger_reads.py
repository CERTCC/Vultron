"""Read a case's ledger: its entries in order, freshness, and tail.

Shared by the SYNC log-replication workflows.
"""

from collections.abc import Sequence
from typing import Any

from pydantic import ValidationError

from vultron.core.models._helpers import (
    project_wire_snapshot_to_core,
)
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.ledger_position import (
    LedgerPosition,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.errors import (
    VultronValidationError,
)


def sorted_case_ledger_entries(
    datalayer: CasePersistence, case_id: str
) -> list[CaseLedgerEntry]:
    """Return the case's canonical ledger entries, ascending by ``log_index``."""
    entries = [
        obj
        for obj in datalayer.list_objects("CaseLedgerEntry")
        if isinstance(obj, CaseLedgerEntry) and obj.case_id == case_id
    ]
    entries.sort(key=lambda log_entry: log_entry.log_index)
    return entries


def case_status_from_snapshot(status_data: Any) -> CaseStatus:
    """The ``CaseStatus`` an ``add_case_status_to_case`` entry carries inline.

    Projected, not validated raw: the snapshot is AS2-shaped, and its
    timestamps are the CASE_MANAGER's to carry (CLP-15-007).

    Raises:
        VultronValidationError: *status_data* is not an inline status with an
            id, or is not a valid ``CaseStatus`` (ARCH-15-001).
    """
    if not isinstance(status_data, dict) or not status_data.get("id"):
        raise VultronValidationError(
            "add_case_status_to_case entry carries no inline CaseStatus"
        )
    try:
        return CaseStatus.model_validate(
            project_wire_snapshot_to_core(CaseStatus, status_data)
        )
    except ValidationError as exc:
        raise VultronValidationError(
            f"CaseStatus '{status_data['id']}' in the entry is malformed: {exc}"
        ) from exc


def _get_case_genesis_hash(case_id: str, dl: CasePersistence) -> str:
    """Return the per-case genesis hash for *case_id* from the DataLayer.

    Looks up the :class:`~vultron.core.models.case.VulnerabilityCase` in *dl*
    and returns its ``genesis_hash`` field.  Returns ``""`` when the case is
    not found or has no genesis hash recorded.  Callers that require a
    non-empty genesis hash MUST treat ``""`` as an error condition.

    Args:
        case_id: URI of the :class:`~vultron.core.models.case.VulnerabilityCase`.
        dl: DataLayer to query.

    Returns:
        64-character hex SHA-256 genesis hash, or ``""`` if unavailable.
    """
    case_obj = dl.read_case(case_id)
    genesis = case_obj.genesis_hash if case_obj is not None else ""
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
    ``(False, reason)`` if any hash mismatch or missing genesis metadata is
    found.

    An empty local log (no entries yet) is considered trivially fresh: the
    actor's acknowledged prefix is the empty prefix, which is contiguous.
    This satisfies SYNC-10-005 — the gate MUST NOT require the actor's tip to
    equal the CaseActor's current tip.

    When *genesis_hash* is ``None``, it is looked up from the DataLayer via
    :func:`_get_case_genesis_hash`.  When the genesis hash cannot be
    determined (case not found or stored with an empty genesis hash),
    ``(False, reason)`` is returned — the check is **fail-closed** per
    CLP-08-003/CLP-08-004.

    Spec: SYNC-10-003, SYNC-10-004, SYNC-10-005, CLP-04-008, CLP-08-004.

    Args:
        case_id: URI of the case whose local ledger to check.
        dl: The actor-local DataLayer to query.
        genesis_hash: Expected ``prev_log_hash`` of the first entry.  When
            ``None`` (default), looked up automatically from *dl*.

    Returns:
        A 2-tuple ``(is_fresh, reason)``.  ``reason`` is an empty string when
        fresh; a human-readable explanation when stale or when genesis
        metadata is unavailable.
    """
    entries: list[CaseLedgerEntry] = [
        obj
        for obj in dl.list_objects("CaseLedgerEntry")
        if isinstance(obj, CaseLedgerEntry) and obj.case_id == case_id
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
    if not effective_genesis:
        return False, (
            f"genesis hash unavailable for case '{case_id}': "
            "cannot verify origin binding of the first ledger entry "
            "(CLP-08-004)"
        )
    if first.prev_log_hash != effective_genesis:
        return False, (
            f"genesis entry prev_log_hash mismatch: "
            f"got {first.prev_log_hash!r}, "
            f"want per-case genesis hash {effective_genesis[:16]!r}…"
        )

    for i in range(1, len(entries)):
        prev = entries[i - 1]
        curr = entries[i]
        if curr.prev_log_hash != prev.entry_hash:
            return False, (
                f"hash mismatch at index {curr.log_index}: "
                f"prev_log_hash={curr.prev_log_hash!r} != "
                f"preceding entry_hash={prev.entry_hash!r}"
            )

    return True, ""


def reconstruct_tail_hash(
    case_id: str, dl: CasePersistence
) -> tuple[str, int]:
    """Return the hash and index of the last stored entry for *case_id*.

    When no entries are stored locally for *case_id*, returns the per-case
    genesis hash (looked up from the DataLayer) and index ``-1``.  If the
    case's genesis hash is not available in the DataLayer, raises
    :exc:`~vultron.errors.VultronValidationError` — the ledger cannot be
    safely bootstrapped without a known genesis anchor (fail-closed per
    CLP-08-004/CLP-08-005).

    Spec: CLP-08-005.

    Args:
        case_id: URI of the parent :class:`VulnerabilityCase`.
        dl: DataLayer to query.

    Returns:
        A 2-tuple ``(tail_hash, tail_index)``.

    Raises:
        VultronValidationError: When the ledger is empty and the per-case
            genesis hash cannot be found in the DataLayer.
    """
    all_entries: list[CaseLedgerEntry] = [
        obj
        for obj in dl.list_objects("CaseLedgerEntry")
        if isinstance(obj, CaseLedgerEntry) and obj.case_id == case_id
    ]

    if not all_entries:
        genesis = _get_case_genesis_hash(case_id, dl)
        if not genesis:
            raise VultronValidationError(
                f"Cannot reconstruct tail hash for case '{case_id}': "
                "ledger is empty and per-case genesis hash is unavailable "
                "in the DataLayer — cannot bootstrap an unanchored chain "
                "(CLP-08-005)."
            )
        return genesis, -1

    all_entries.sort(key=lambda entry: entry.log_index)
    last = all_entries[-1]
    return last.entry_hash, last.log_index


def first_case_with_ledger(
    case_ids: Sequence[str], dl: CasePersistence
) -> str | None:
    """The one of *case_ids* whose ledger *dl* holds, or ``None`` for none.

    *dl* holds a case's ledger once it stores the case with its per-case
    genesis hash, the anchor of an empty chain (CLP-08-004), or an entry of
    its chain: the CASE_MANAGER from creating the case, a participant from
    its first copy or entry.  Before that it has no tail to state, so its
    activities about the case carry no ``ledgerPosition`` (SYNC-18-017), and
    :func:`ledger_tail_position` would raise.  ``None`` is an answer, not a
    failure: the sender holds no ledger for any of them.

    Each id is first read as a case (one keyed read), and the first id naming
    a case *dl* stores with its genesis hash wins; only when none does are the
    stored entries listed, once, and the first id with a stored chain wins.  A
    stored case is so preferred over an earlier id held only by its chain,
    which keeps the entry table off the common path.
    """
    for case_id in case_ids:
        if _get_case_genesis_hash(case_id, dl):
            return case_id
    if not case_ids:
        return None
    chained = {
        obj.case_id
        for obj in dl.list_objects("CaseLedgerEntry")
        if isinstance(obj, CaseLedgerEntry)
    }
    return next((case_id for case_id in case_ids if case_id in chained), None)


def ledger_tail_position(case_id: str, dl: CasePersistence) -> LedgerPosition:
    """Return the position of the last ledger entry *dl* holds for *case_id*.

    For the CASE_MANAGER this is the authoritative tail it stamps on a
    full-case Invite (CM-11-031); for a participant it is the tail of its own
    replica, which it stamps on its reply (CM-11-011).  An empty ledger's
    position is ``(-1, genesis_hash)`` (CLP-08-004).

    Raises:
        VultronValidationError: When the ledger is empty and the case's
            genesis hash is unavailable (see :func:`reconstruct_tail_hash`).
    """
    tail_hash, tail_index = reconstruct_tail_hash(case_id, dl)
    return LedgerPosition(log_index=tail_index, entry_hash=tail_hash)
