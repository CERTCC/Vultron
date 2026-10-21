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

"""Hold an out-of-order ``Announce(CaseLedgerEntry)`` as it was received.

A participant that cannot apply a received ledger entry yet holds the
``Announce`` that carried it, never the entry alone (SYNC-14-001,
SYNC-15-004): the body intake archived is held for the inbox replay in a
:class:`~vultron.core.models.deferred_inbox_activity.DeferredInboxActivity`
(IO-03-004), and a
:class:`~vultron.core.models.held_ledger_announce.HeldLedgerAnnounce` row,
keyed on the entry's ``prev_log_hash``, finds it again when the chain tail
reaches it.  The drain replays that held ``Announce`` through the inbox
(SYNC-14-009), so what is applied is what the CASE_MANAGER sent.

The holding area is per case and bounded (SYNC-14-006): when full, the held
``Announce`` farthest ahead of the gap (highest ``log_index``) is dropped
with a warning, or the new one when it is itself the farthest.  A dropped
``Announce`` is recovered by the ``Reject(CaseLedgerEntry)`` already sent for
it (SYNC-14-002), never by the drop.

Spec: SYNC-14-001, SYNC-14-005, SYNC-14-006, SYNC-14-009, SYNC-15-004.
"""

import logging

from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.deferred_inbox_activity import DeferredInboxActivity
from vultron.core.models.held_ledger_announce import HeldLedgerAnnounce
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.errors import VultronWiringError

logger = logging.getLogger(__name__)

#: Default bound on the ``Announce``\ s held per case (SYNC-14-006).  Sized
#: generously against any realistic reorder window, while still bounding what
#: a misbehaving peer can make a receiver hold.
DEFAULT_HELD_LEDGER_ANNOUNCES_MAX: int = 256

_HELD_TYPE = "HeldLedgerAnnounce"


def held_ledger_announces(
    dl: CasePersistence, case_id: str
) -> list[HeldLedgerAnnounce]:
    """Every ``Announce`` held for *case_id*, in ``log_index`` order."""
    held = [
        obj
        for obj in dl.list_objects(_HELD_TYPE)
        if isinstance(obj, HeldLedgerAnnounce) and obj.case_id == case_id
    ]
    return sorted(held, key=lambda h: h.log_index)


def held_successor(
    dl: CasePersistence, case_id: str, tail_hash: str
) -> HeldLedgerAnnounce | None:
    """The held ``Announce`` whose entry extends *tail_hash*, if any."""
    held = dl.read(HeldLedgerAnnounce.build_id(case_id, tail_hash))
    return held if isinstance(held, HeldLedgerAnnounce) else None


def holds_held_body(dl: CasePersistence, held: HeldLedgerAnnounce) -> bool:
    """Whether the received body of *held* is still held for its replay."""
    return isinstance(
        dl.read(DeferredInboxActivity.build_id(held.activity_id)),
        DeferredInboxActivity,
    )


def release_held(dl: CasePersistence, held: HeldLedgerAnnounce) -> None:
    """Drop the index row of an ``Announce`` handed to the inbox replay.

    The held body stays: the replay reads it and deletes it (IO-03-004).
    """
    dl.delete(_HELD_TYPE, held.id_)


def discard_held(dl: CasePersistence, held: HeldLedgerAnnounce) -> None:
    """Drop a held ``Announce`` entirely: its index row and its body."""
    with dl.transaction():
        dl.delete(_HELD_TYPE, held.id_)
        dl.delete(
            "DeferredInboxActivity",
            DeferredInboxActivity.build_id(held.activity_id),
        )


def _received_body(dl: CasePersistence, activity_id: str) -> str:
    """The body intake archived for *activity_id* (CLP-10-017).

    Raises:
        VultronWiringError: When nothing is archived.  Intake archives every
            received activity before any guard, so a hold that finds no body
            runs in a miswired tree, and holding nothing would lose the
            ``Announce``.
    """
    record = dl.read(ReceivedActivityRecord.build_id(activity_id))
    if not isinstance(record, ReceivedActivityRecord):
        raise VultronWiringError(
            f"Announce(CaseLedgerEntry) '{activity_id}' is not archived, so"
            " there is no received body to hold for its replay (CLP-10-017,"
            " SYNC-14-001)"
        )
    return record.received_body


def _make_room(
    dl: CasePersistence,
    entry: CaseLedgerEntry,
    max_per_case: int,
) -> bool:
    """Free a slot for *entry* in a full holding area, if it may have one.

    Returns ``False`` when *entry* is itself the farthest ahead of the gap,
    so it is the one dropped (SYNC-14-006).
    """
    held = held_ledger_announces(dl, entry.case_id)
    if len(held) < max_per_case:
        return True
    if not held or entry.log_index >= held[-1].log_index:
        logger.warning(
            "held ledger announces: holding area full for case %s (max=%d);"
            " not holding far-future entry index=%d",
            entry.case_id,
            max_per_case,
            entry.log_index,
        )
        return False
    farthest = held[-1]
    discard_held(dl, farthest)
    logger.warning(
        "held ledger announces: holding area full for case %s (max=%d);"
        " dropped the Announce '%s' of farthest-ahead entry index=%d to hold"
        " index=%d",
        entry.case_id,
        max_per_case,
        farthest.activity_id,
        farthest.log_index,
        entry.log_index,
    )
    return True


def hold_ledger_announce(
    dl: CasePersistence,
    entry: CaseLedgerEntry,
    activity_id: str,
    max_per_case: int | None = None,
) -> bool:
    """Hold the received ``Announce`` *activity_id* until *entry* applies.

    Holds the body intake archived, as the inbox holds a deferred activity
    (``DeferredInboxActivity``, IO-03-004), and indexes it under the entry's
    case and ``prev_log_hash``.  An ``Announce`` whose entry is already held
    under the same predecessor is not held again, whatever its id; a
    different entry under the same predecessor (a fork) replaces the held
    one, with a warning.  When the case's holding area is full, the bound
    applies (SYNC-14-006): *max_per_case*, by default
    :data:`DEFAULT_HELD_LEDGER_ANNOUNCES_MAX`.

    Returns:
        ``True`` when the entry's ``Announce`` is now held, ``False`` when
        the bound dropped it.

    Raises:
        VultronWiringError: When intake archived no body for *activity_id*.
    """
    existing = held_successor(dl, entry.case_id, entry.prev_log_hash)
    if existing is not None and existing.entry_hash == entry.entry_hash:
        logger.debug(
            "held ledger announces: entry '%s' is already held in Announce"
            " '%s'",
            entry.id_,
            existing.activity_id,
        )
        return True
    received_body = _received_body(dl, activity_id)
    if existing is not None:
        logger.warning(
            "held ledger announces: replacing forked held entry for case %s"
            " prev_log_hash=%.16s… (old index=%d in '%s', new index=%d in"
            " '%s')",
            entry.case_id,
            entry.prev_log_hash,
            existing.log_index,
            existing.activity_id,
            entry.log_index,
            activity_id,
        )
        discard_held(dl, existing)
    elif not _make_room(
        dl,
        entry,
        DEFAULT_HELD_LEDGER_ANNOUNCES_MAX
        if max_per_case is None
        else max_per_case,
    ):
        return False

    body_id = DeferredInboxActivity.build_id(activity_id)
    with dl.transaction():
        # A body already held for a replay is the same delivery's; keep it.
        if not isinstance(dl.read(body_id), DeferredInboxActivity):
            dl.create(
                DeferredInboxActivity(
                    activity_id=activity_id, received_body=received_body
                )
            )
        dl.save(
            HeldLedgerAnnounce(
                case_id=entry.case_id,
                prev_log_hash=entry.prev_log_hash,
                log_index=entry.log_index,
                entry_hash=entry.entry_hash,
                entry_id=entry.id_,
                activity_id=activity_id,
            )
        )
    logger.debug(
        "held ledger announces: holding Announce '%s' of entry '%s' for case"
        " %s (index=%d, prev_log_hash=%.16s…)",
        activity_id,
        entry.id_,
        entry.case_id,
        entry.log_index,
        entry.prev_log_hash,
    )
    return True


__all__ = [
    "DEFAULT_HELD_LEDGER_ANNOUNCES_MAX",
    "discard_held",
    "held_ledger_announces",
    "held_successor",
    "hold_ledger_announce",
    "holds_held_body",
    "release_held",
]
