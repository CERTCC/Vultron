"""Find the ledger entries that record an activity, and their equivalents.

Idempotency for a ledgered assertion compares what an entry asserts, not
the timestamps stamped when its snapshot was built (CLP-14-011).
"""

from datetime import datetime
from typing import Any

from vultron.core.models._helpers import (
    parse_published,
)
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.predicates.addressing import snapshot_actor_id

#: Top-level snapshot fields that may be stamped when a snapshot is *built*
#: rather than carried from the assertion it records.  The CaseActor's own
#: activities carry its clock as ``published`` at build time (CLP-14-011), so
#: building one afresh for a retry yields a new value.  Treating it as part of what an entry asserts
#: makes idempotency a race against the clock — ``now_utc`` truncates to whole
#: seconds, so a retry that lands in the next second appends a duplicate while
#: one in the same second does not.
#:
#: It is *not* true of the top-level ``published`` on a received activity: that
#: is the sender's claimed event time, carried across the wire→core boundary
#: (ISSUE-3149) and load-bearing for CLP-14-007/008/013 and CLP-15-003.
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
