"""Shared helpers for SYNC log-replication workflows."""

import logging
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from vultron.core.models._helpers import (
    parse_published,
    project_wire_snapshot_to_core,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.ledger_position import (
    EMPTY_LEDGER_LOG_INDEX,
    LedgerPosition,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.predicates.addressing import snapshot_actor_id
from vultron.errors import (
    VultronEntryRefusedError,
    VultronNotFoundError,
    VultronValidationError,
)

logger = logging.getLogger(__name__)


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
    activities about the case carry no ``ledgerPosition`` (SYNC-18-001), and
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
    full-case Invite (CM-11-010); for a participant it is the tail of its own
    replica, which it stamps on its reply (CM-11-011).  An empty ledger's
    position is ``(-1, genesis_hash)`` (CLP-08-004).

    Raises:
        VultronValidationError: When the ledger is empty and the case's
            genesis hash is unavailable (see :func:`reconstruct_tail_hash`).
    """
    tail_hash, tail_index = reconstruct_tail_hash(case_id, dl)
    return LedgerPosition(log_index=tail_index, entry_hash=tail_hash)


def store_ledger_entry(
    entry: CaseLedgerEntry, dl: CasePersistence
) -> VulnerabilityCase:
    """Store *entry* and move its case's ``ledger_position`` to it, as one write.

    The one place a case's position moves (SYNC-16-005): the CASE_MANAGER's
    commit (``PersistLogEntryNode``) and a replica's store
    (``PersistReceivedLogEntryNode``) both call it.  The case file is the
    projection of its ledger up to its position (ADR-0124), so storing an
    entry and naming it as the case's position commit together or not at all
    (ADR-0146).  Moving the position is part of applying the entry, not a
    change to the case file of its own, so it takes no entry (CLP-07-013).

    The entry's own snapshot was built before this runs, so a snapshot that
    carries the case names the position before the entry, and no entry's hash
    depends on itself.

    The position never moves back.  A replica whose case a copy seeded or
    replaced ahead of its chain stores the entries at or before the copy's
    position as idempotent no-ops (SYNC-16-007): the entry is stored and the
    case stays at the copy's position, which already reflects it.  An entry
    at the position's index with another hash is refused, not stored: the
    chain would name one entry there and the case another.

    Returns:
        The case as stored, at its new position.

    Raises:
        VultronNotFoundError: *dl* holds no case for the entry; a ledger entry
            belongs to a stored case, whose genesis hash anchors it.
        VultronEntryRefusedError: *entry* is at the index the case's position
            names, with another hash (SYNC-16-007).
    """
    with dl.transaction():
        case = dl.read_case(entry.case_id)
        if case is None:
            raise VultronNotFoundError("VulnerabilityCase", entry.case_id)
        held = case.ledger_position
        if (
            entry.log_index == held.log_index
            and entry.entry_hash != held.entry_hash
        ):
            raise VultronEntryRefusedError(
                f"ledger entry '{entry.id_}' is at index {entry.log_index}"
                f" with hash {entry.entry_hash:.16}…, but case"
                f" '{entry.case_id}' names {held.entry_hash:.16}… there: the"
                " chains conflict (SYNC-16-007)"
            )
        dl.save(entry)
        if entry.log_index <= held.log_index:
            return case
        case.ledger_position = LedgerPosition(
            log_index=entry.log_index, entry_hash=entry.entry_hash
        )
        dl.save(case)
    return case


def at_stored_position(
    case: VulnerabilityCase, dl: CasePersistence
) -> VulnerabilityCase:
    """*case* at the ledger position *dl*'s stored copy of it names.

    Only :func:`store_ledger_entry` moves a case's position.  A node that
    reads the case, commits entries and then saves or snapshots the copy it
    read holds the position from before those commits; this brings the copy
    up to the stored position, so the save does not put the position back and
    a snapshot names the position before its own entry (SYNC-16-005).
    Returns *case* itself when the positions already agree or *dl* holds no
    copy yet.
    """
    stored = dl.read_case(case.id_)
    if stored is None or stored.ledger_position == case.ledger_position:
        return case
    # A copy, not an assignment: the caller's object stays as it read it,
    # and the stored position is already a validated one for this case.
    return case.model_copy(update={"ledger_position": stored.ledger_position})


def ledger_position_refusal(
    case_id: str,
    dl: CasePersistence,
    *,
    position: LedgerPosition,
    floor: LedgerPosition,
) -> str | None:
    """Return why *position* is not an acceptable reply position, or ``None``.

    The Invite's position is a floor, not a pin (CM-11-012, ADR-0121).  A
    position is refused when it is absent, is behind *floor*, or names an
    entry *dl* does not hold at that index.  One at or beyond the floor that
    names a held entry is accepted.

    Args:
        case_id: URI of the case whose ledger *dl* holds.
        dl: The CASE_MANAGER's store, the authority on what its ledger holds.
        position: The replier's claimed ledger position.
        floor: The full-case Invite's ledger position.
    """
    if position.log_index < floor.log_index:
        return (
            f"ledger position {position.log_index} is behind the Invite's"
            f" floor {floor.log_index} (CM-11-012)"
        )
    if position.log_index == EMPTY_LEDGER_LOG_INDEX:
        held_hash = _get_case_genesis_hash(case_id, dl)
    else:
        held_hash = ""
        for obj in dl.list_objects("CaseLedgerEntry"):
            if (
                isinstance(obj, CaseLedgerEntry)
                and obj.case_id == case_id
                and obj.log_index == position.log_index
            ):
                held_hash = obj.entry_hash
                break
    if not held_hash or held_hash != position.entry_hash:
        return (
            f"ledger position {position.log_index} names an entry the"
            " ledger does not hold (CM-11-012)"
        )
    return None


#: Top-level snapshot fields that may be stamped when a snapshot is *built*
#: rather than carried from the assertion it records.  The CaseActor's own
#: activities carry its clock as ``published`` at build time (CLP-14-002), so
#: building one afresh for a retry yields a new value.  Treating it as part of what an entry asserts
#: makes idempotency a race against the clock — ``now_utc`` truncates to whole
#: seconds, so a retry that lands in the next second appends a duplicate while
#: one in the same second does not.
#:
#: It is *not* true of the top-level ``published`` on a received activity: that
#: is the sender's claimed event time, carried across the wire→core boundary
#: (ISSUE-3149) and load-bearing for CLP-14-006/007/008 and CLP-15-003.
#: Excluding it from the *equivalence* comparison is still correct — two
#: deliveries of one assertion are the same assertion whatever their
#: timestamps — but do not read this set as a claim that
#: ``payloadSnapshot.published`` is meaningless.  See
#: :func:`_find_prev_actor_published`, which depends on it being real.
_VOLATILE_SNAPSHOT_KEYS = frozenset({"published", "updated"})


def _semantic_payload(value: Any) -> Any:
    """Return *value* without its top-level build-time timestamps.

    Top level only.  The objects a snapshot embeds carry their own time — the
    time they were authored with, or the sender's as received — and rendering
    them does not change it (ISSUE-2553, ISSUE-3257).  A nested ``published``
    or ``updated`` that differs is therefore a different object state, and it
    stays in the comparison: dropping it at every depth would fold a genuinely
    new assertion into a recorded one.
    """
    if isinstance(value, dict):
        return {
            key: item
            for key, item in value.items()
            if key not in _VOLATILE_SNAPSHOT_KEYS
        }
    return value


def recorded_entries_for_case(
    *, case_id: str, dl: CasePersistence
) -> list[CaseLedgerEntry]:
    """Return *case_id*'s ledger entries, oldest first, in one store scan.

    :meth:`CasePersistence.list_objects` takes no case filter, so it walks every
    ledger entry in the store regardless of case.  The commit boundary needs
    this list twice — once for the CLP-15-003 predecessor lookup and once for the
    idempotency equivalence check — and scanning twice doubles an already O(N)
    step on every commit (CS-22-001).  Callers that need both pass the result to
    each helper's ``entries`` argument.
    """
    entries = [
        obj
        for obj in dl.list_objects("CaseLedgerEntry")
        if isinstance(obj, CaseLedgerEntry) and obj.case_id == case_id
    ]
    entries.sort(key=lambda entry: entry.log_index)
    return entries


def is_ledgered_activity(
    datalayer: CasePersistence,
    case_id: str,
    activity_id: str,
    *,
    semantic_type: str | None = None,
) -> bool:
    """``True`` when *case_id*'s ledger already records *activity_id*.

    A received activity the ledger already records is a redelivery: its
    effect is in place, so a guard reports it as a repeat (HP-01-003).
    With *semantic_type*, the entry must also record the activity as that
    semantic, so an id reused for a different activity is not taken for it.
    """
    return any(
        entry.log_object_id == activity_id
        and (semantic_type is None or entry.semantic_type == semantic_type)
        for entry in recorded_entries_for_case(case_id=case_id, dl=datalayer)
    )


def _find_equivalent_recorded_entry(
    *,
    case_id: str,
    object_id: str,
    semantic_type: str,
    payload_snapshot: dict[str, Any],
    dl: CasePersistence,
    entries: list[CaseLedgerEntry] | None = None,
) -> CaseLedgerEntry | None:
    """Return an already-recorded canonical entry with equivalent semantics.

    "Equivalent" means same case, object, semantic type, and payload snapshot.
    This supports idempotent handling of participant retries without appending
    duplicate canonical entries for the same logical assertion.

    Snapshots are compared through :func:`_semantic_payload`, so a retry is
    recognised as one even though rebuilding its snapshot restamps the
    snapshot's own top-level ``published``.  Comparing that would make the
    dedup — and with it ADR-0041's ledger-index stability — depend on whether
    the two deliveries happened to land in the same clock second.

    Args:
        case_id: URI of the parent case.
        object_id: Candidate entry's ``log_object_id``.
        semantic_type: Candidate entry's ``semantic_type``.
        payload_snapshot: The candidate ``payloadSnapshot``.
        dl: DataLayer to query when *entries* is not supplied.
        entries: Pre-fetched recorded entries for this case, from
            :func:`recorded_entries_for_case`.  Supplying it avoids a second
            full store scan when the caller already holds the list.
    """
    pool = (
        entries
        if entries is not None
        else recorded_entries_for_case(case_id=case_id, dl=dl)
    )
    wanted = _semantic_payload(payload_snapshot)
    matches: list[CaseLedgerEntry] = [
        obj
        for obj in pool
        if obj.log_object_id == object_id
        and obj.semantic_type == semantic_type
        and _semantic_payload(obj.payload_snapshot) == wanted
    ]
    if not matches:
        return None
    # pool is log_index-ascending (recorded_entries_for_case sorts it) and the
    # loop above preserves that order, so matches[-1] is the highest log_index
    # without a re-sort.
    return matches[-1]


def _find_prev_actor_published(
    *,
    case_id: str,
    payload_snapshot: dict[str, Any],
    dl: CasePersistence,
    entries: list[CaseLedgerEntry] | None = None,
) -> datetime | None:
    """Return the claimed ``published`` this assertion must not regress behind.

    Scans the recorded entries for *case_id*, keeps the ones asserted by the
    same actor as *payload_snapshot*, and returns the claimed ``published`` of
    the highest ``log_index`` among them.  That value is the predecessor
    CLP-15-003 compares the next assertion against.

    Scoped to one actor on purpose.  CLP-15-003 places its obligation on
    timestamps "within the same participant's event stream"; ADR-0079 rejected
    comparing wall-clock times across actors (option C) because their clocks
    are not synchronised.  A cross-actor comparison here would reject
    well-formed assertions whenever two participants' clocks disagreed.

    Returns ``None`` when this exact assertion is *already* recorded, because a
    redelivery is not a new event in the stream and CLP-15-003 has nothing to
    say about it.  Without that carve-out the ordering report and the idempotency
    path (:func:`_find_equivalent_recorded_entry`) contradict each other: a
    retry of assertion A that arrives after the actor's later assertion B would
    be reported as a regression instead of being recognised as the duplicate it
    is.  Out-of-order and retried delivery is a designed-for condition
    (ADR-0037), so it must not be reported as a participant fault.

    Args:
        case_id: URI of the parent case.
        payload_snapshot: The candidate ``payloadSnapshot``.  An empty or
            actor-less snapshot has no stream to compare against.
        dl: DataLayer to query when *entries* is not supplied.
        entries: Pre-fetched recorded entries for this case, from
            :func:`recorded_entries_for_case`.  Supplying it avoids a second
            full store scan when the caller already holds the list.

    Returns:
        The predecessor's claimed ``published``; ``None`` when this actor has no
        prior recorded assertion on this case, when this assertion is itself
        already recorded, or when the predecessor's claim was unparseable.
    """
    # One actor's stream whatever spelling each assertion used: the
    # snapshots keep the sender's (OID-01-006).
    snapshot_actor = snapshot_actor_id(payload_snapshot.get("actor"))
    if not snapshot_actor:
        return None
    pool = (
        entries
        if entries is not None
        else recorded_entries_for_case(case_id=case_id, dl=dl)
    )
    wanted = _semantic_payload(payload_snapshot)
    matches: list[CaseLedgerEntry] = []
    for obj in pool:
        if snapshot_actor_id(obj.payload_snapshot.get("actor")) != (
            snapshot_actor
        ):
            continue
        if _semantic_payload(obj.payload_snapshot) == wanted:
            return None  # redelivery, not a new event in this actor's stream
        matches.append(obj)
    if not matches:
        return None
    # pool is log_index-ascending (recorded_entries_for_case sorts it) and the
    # loop above preserves that order, so matches[-1] is this actor's highest
    # log_index without a re-sort.
    return parse_published(matches[-1].payload_snapshot.get("published"))
