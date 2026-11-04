"""Store a ledger entry and check a stamped ledger position against the store.

Shared by the SYNC log-replication workflows.
"""

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.ledger_position import (
    EMPTY_LEDGER_LOG_INDEX,
    LedgerPosition,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.sync_helpers.ledger_reads import _get_case_genesis_hash
from vultron.errors import (
    VultronEntryRefusedError,
    VultronNotFoundError,
)


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
    position as idempotent no-ops (SYNC-16-023): the entry is stored and the
    case stays at the copy's position, which already reflects it.  An entry
    at the position's index with another hash is refused, not stored: the
    chain would name one entry there and the case another.

    Returns:
        The case as stored, at its new position.

    Raises:
        VultronNotFoundError: *dl* holds no case for the entry; a ledger entry
            belongs to a stored case, whose genesis hash anchors it.
        VultronEntryRefusedError: *entry* is at the index the case's position
            names, with another hash (SYNC-16-025).
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
                " chains conflict (SYNC-16-025)"
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


def holds_ledger_position(
    case_id: str, dl: CasePersistence, position: LedgerPosition
) -> bool:
    """Whether *dl*'s ledger for *case_id* holds *position*.

    True when the entry *dl* holds at the position's index has the
    position's hash; at index -1 (an empty ledger) the hash to match is the
    case's genesis hash (CLP-08-004).  An index past the tail names no entry,
    so it is not held.  The CASE_MANAGER is the single writer, so a position
    it does not hold is one its ledger never had (CM-11-012, SYNC-18-005).
    """
    if position.log_index == EMPTY_LEDGER_LOG_INDEX:
        held_hash = _get_case_genesis_hash(case_id, dl)
    else:
        held_hash = next(
            (
                obj.entry_hash
                for obj in dl.list_objects("CaseLedgerEntry")
                if isinstance(obj, CaseLedgerEntry)
                and obj.case_id == case_id
                and obj.log_index == position.log_index
            ),
            "",
        )
    return bool(held_hash) and held_hash == position.entry_hash


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
    if not holds_ledger_position(case_id, dl, position):
        return (
            f"ledger position {position.log_index} names an entry the"
            " ledger does not hold (CM-11-012)"
        )
    return None
