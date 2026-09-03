"""Shared helpers for SYNC log-replication workflows."""

import logging
from datetime import datetime
from typing import Any

from vultron.core.models._helpers import parse_published
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.ports.case_persistence import CasePersistence
from vultron.errors import VultronValidationError

logger = logging.getLogger(__name__)


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
    ``(False, reason)`` if any index gap, hash mismatch, or missing genesis
    metadata is found.

    An empty local log (no entries yet) is considered trivially fresh: the
    actor's acknowledged prefix is the empty prefix, which is contiguous.
    This satisfies SYNC-10-005 — the gate MUST NOT require the actor's tip to
    equal the CaseActor's current tip.

    When *genesis_hash* is ``None``, it is looked up from the DataLayer via
    :func:`_get_case_genesis_hash`.  When the genesis hash cannot be
    determined (case not found or stored with an empty genesis hash),
    ``(False, reason)`` is returned — the check is **fail-closed** per
    CLP-08-003/CLP-08-004.

    Spec: SYNC-10-003, SYNC-10-004, SYNC-10-005, CLP-08-004.

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
    entries: list[CaseLedgerEntry] = [
        obj
        for obj in dl.list_objects("CaseLedgerEntry")
        if isinstance(obj, CaseLedgerEntry) and obj.case_id == case_id
    ]

    if not entries:
        genesis = _get_case_genesis_hash(case_id, dl)
        if not genesis:
            raise VultronValidationError(
                f"Cannot reconstruct tail hash for case '{case_id}': "
                "ledger is empty and per-case genesis hash is unavailable "
                "in the DataLayer — cannot bootstrap an unanchored chain "
                "(CLP-08-005)."
            )
        return genesis, -1

    entries.sort(key=lambda entry: entry.log_index)
    last = entries[-1]
    return last.entry_hash, last.log_index


#: Wire fields that may be stamped when a snapshot is *built* rather than
#: carried from the object it describes.  ``as_Base`` declares ``published`` and
#: ``updated`` with ``default_factory=now_utc``, and core status objects hold no
#: timestamp of their own to supply, so re-rendering one stored object twice
#: yields two different values.  They are therefore not part of what an entry
#: asserts, and treating them as such makes idempotency a race against the
#: clock — ``now_utc`` truncates to whole seconds, so a retry that lands in the
#: next second appends a duplicate while one in the same second does not.
#:
#: This holds for every CaseActor-authored snapshot, which is what makes the
#: exclusion necessary.  It is *not* true of the top-level ``published`` on a
#: received activity: that is the sender's claimed event time, carried across
#: the wire→core boundary (ISSUE-3149) and load-bearing for CLP-14-006/007/008
#: and CLP-15-003.  Excluding it from the *equivalence* comparison is still
#: correct — two deliveries of one assertion are the same assertion whatever
#: their timestamps — but do not read this set as a claim that
#: ``payloadSnapshot.published`` is meaningless.  See
#: :func:`_find_prev_actor_published`, which depends on it being real.
_VOLATILE_SNAPSHOT_KEYS = frozenset({"published", "updated"})


def _semantic_payload(value: Any) -> Any:
    """Return *value* with build-time timestamps dropped at every depth.

    Recursive because the drift is nested as well as top-level: an
    ``add_participant_status_to_participant`` snapshot embeds the whole
    re-rendered participant as its ``target``, so every entry of that
    participant's ``participantStatuses`` list carries its own freshly stamped
    pair.

    Only the two keys are dropped.  Where a timestamp *is* load-bearing it is
    still compared through its consequences — a case's ``published`` feeds
    ``genesis_hash`` (CLP-08-002), which stays in the comparison.
    """
    if isinstance(value, dict):
        return {
            key: _semantic_payload(item)
            for key, item in value.items()
            if key not in _VOLATILE_SNAPSHOT_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_semantic_payload(item) for item in value]
    return value


def _find_equivalent_recorded_entry(
    *,
    case_id: str,
    object_id: str,
    event_type: str,
    payload_snapshot: dict[str, Any],
    dl: CasePersistence,
) -> CaseLedgerEntry | None:
    """Return an already-recorded canonical entry with equivalent semantics.

    "Equivalent" means same case, object, event type, and payload snapshot.
    This supports idempotent handling of participant retries without appending
    duplicate canonical entries for the same logical assertion.

    Snapshots are compared through :func:`_semantic_payload`, so a retry is
    recognised as one even though rebuilding its snapshot restamps every
    ``published``/``updated`` field it embeds.  Comparing those would make the
    dedup — and with it ADR-0041's ledger-index stability — depend on whether
    the two deliveries happened to land in the same clock second.
    """
    wanted = _semantic_payload(payload_snapshot)
    matches: list[CaseLedgerEntry] = [
        obj
        for obj in dl.list_objects("CaseLedgerEntry")
        if isinstance(obj, CaseLedgerEntry)
        and obj.case_id == case_id
        and obj.disposition == "recorded"
        and obj.log_object_id == object_id
        and obj.event_type == event_type
        and _semantic_payload(obj.payload_snapshot) == wanted
    ]
    if not matches:
        return None
    matches.sort(key=lambda entry: entry.log_index)
    return matches[-1]


def _find_prev_actor_published(
    *,
    case_id: str,
    payload_snapshot: dict[str, Any],
    dl: CasePersistence,
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
    say about it.  Without that carve-out the ordering check and the idempotency
    path (:func:`_find_equivalent_recorded_entry`) contradict each other: a
    retry of assertion A that arrives after the actor's later assertion B would
    be rejected as a regression instead of being recognised as the duplicate it
    is.  Out-of-order and retried delivery is a designed-for condition
    (ADR-0037), so the ordering check must not turn one into a hard failure.

    Args:
        case_id: URI of the parent case.
        payload_snapshot: The candidate ``payloadSnapshot``.  An empty or
            actor-less snapshot has no stream to compare against.
        dl: DataLayer to query.

    Returns:
        The predecessor's claimed ``published``; ``None`` when this actor has no
        prior recorded assertion on this case, when this assertion is itself
        already recorded, or when the predecessor's claim was unparseable.
    """
    snapshot_actor = payload_snapshot.get("actor")
    if not snapshot_actor:
        return None
    wanted = _semantic_payload(payload_snapshot)
    matches: list[CaseLedgerEntry] = []
    for obj in dl.list_objects("CaseLedgerEntry"):
        if (
            not isinstance(obj, CaseLedgerEntry)
            or obj.case_id != case_id
            or obj.disposition != "recorded"
            or obj.payload_snapshot.get("actor") != snapshot_actor
        ):
            continue
        if _semantic_payload(obj.payload_snapshot) == wanted:
            return None  # redelivery, not a new event in this actor's stream
        matches.append(obj)
    if not matches:
        return None
    matches.sort(key=lambda entry: entry.log_index)
    return parse_published(matches[-1].payload_snapshot.get("published"))
