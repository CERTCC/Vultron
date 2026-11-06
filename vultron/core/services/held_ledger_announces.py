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
``Announce`` that carried it, never the entry alone (SYNC-14-010,
SYNC-15-004): the body intake recorded is marked as owing a replay on its own
:class:`~vultron.core.models.received_activity_record.ReceivedActivityRecord`
(IO-03-009, ADR-0154), and a
:class:`~vultron.core.models.held_ledger_announce.HeldLedgerAnnounce` row,
keyed on the entry's ``prev_log_hash``, finds it again when the chain tail
reaches it.  The drain replays that held ``Announce`` through the inbox
(SYNC-14-009), so what is applied is what the CASE_MANAGER sent.

This hold is the one that lands on a record intake already wrote: the
``Announce`` passed its doors and intake recorded it, ``HELD`` (``HANDLED`` on
a re-run), before the handler found the gap.  The hold makes it ``HELD`` with
its body, not archived, until
its replay applies it (ADR-0154): releasing it hands the body to the replay,
which records it again as a delivery of its own, and discarding it (the
bound, SYNC-14-013, or a fork's replacement) drops the message, body and all
(``received_holding``).

The holding area is per case and bounded (SYNC-14-006): when full, the held
``Announce`` farthest ahead of the gap (highest ``log_index``) is dropped
with a warning, or the new one when it is itself the farthest (SYNC-14-013).
A dropped ``Announce`` is recovered by the ``Reject(CaseLedgerEntry)`` already
sent for it (SYNC-14-002), never by the drop (SYNC-14-014).

Spec: SYNC-14-001, SYNC-14-005, SYNC-14-006, SYNC-14-009, SYNC-15-004.
"""

import logging

from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.held_ledger_announce import HeldLedgerAnnounce
from vultron.core.models.received_activity_record import HOLDING_STAGES
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.received_activity import (
    held_received_record,
    sealed_body_of,
)
from vultron.core.services.received_holding import (
    discard_holding,
    hold_for_replay,
    owes_replay,
)
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
    return owes_replay(dl, held.activity_id)


def release_held(dl: CasePersistence, held: HeldLedgerAnnounce) -> None:
    """Drop the index row of an ``Announce`` handed to the inbox replay.

    The held body stays: the replay reads it and releases it (IO-03-009).
    """
    dl.delete(_HELD_TYPE, held.id_)


def discard_held(dl: CasePersistence, held: HeldLedgerAnnounce) -> None:
    """Drop a held ``Announce``: its index row and its held record.

    The ``Announce`` was never applied, so it leaves no archive; its
    recovery is the ``Reject(CaseLedgerEntry)`` already sent for it, whose
    answer is a delivery the receiver has not seen (SYNC-14-014).
    """
    with dl.transaction():
        dl.delete(_HELD_TYPE, held.id_)
        discard_holding(dl, held.activity_id)


def _received_body(dl: CasePersistence, activity_id: str) -> str:
    """The body intake recorded for *activity_id* (CLP-10-017).

    Raises:
        VultronWiringError: When intake recorded no body in holding.  Intake
            records every received activity its doors admit, ahead of the
            handling tree, so a hold that finds none runs in a miswired
            tree, and holding nothing would lose the ``Announce``.
    """
    record = held_received_record(dl, activity_id)
    if record is None or record.stage not in HOLDING_STAGES:
        raise VultronWiringError(
            f"Announce(CaseLedgerEntry) '{activity_id}' is not in holding, so"
            " there is no received body to hold for its replay (CLP-10-017,"
            " SYNC-14-001)"
        )
    return sealed_body_of(record)


def _make_room(
    dl: CasePersistence,
    entry: CaseLedgerEntry,
    activity_id: str,
    max_per_case: int,
    actor_id: str | None,
) -> bool:
    """Free a slot for *entry* in a full holding area, if it may have one.

    Returns ``False`` when *entry* is itself the farthest ahead of the gap,
    so it is the one dropped (SYNC-14-013).
    """
    held = held_ledger_announces(dl, entry.case_id)
    if len(held) < max_per_case:
        return True
    if not held or entry.log_index >= held[-1].log_index:
        logger.warning(
            "held ledger announces: holding area full for case %s (max=%d,"
            " actor %s); not holding Announce '%s' of far-future entry"
            " index=%d",
            entry.case_id,
            max_per_case,
            actor_id,
            activity_id,
            entry.log_index,
        )
        return False
    farthest = held[-1]
    discard_held(dl, farthest)
    logger.warning(
        "held ledger announces: holding area full for case %s (max=%d,"
        " actor %s); dropped the Announce '%s' of farthest-ahead entry"
        " index=%d to hold Announce '%s' of index=%d",
        entry.case_id,
        max_per_case,
        actor_id,
        farthest.activity_id,
        farthest.log_index,
        activity_id,
        entry.log_index,
    )
    return True


def hold_ledger_announce(
    dl: CasePersistence,
    entry: CaseLedgerEntry,
    activity_id: str,
    max_per_case: int | None = None,
    *,
    actor_id: str | None = None,
) -> bool:
    """Hold the received ``Announce`` *activity_id* until *entry* applies.

    Marks the body intake recorded as owing a replay, as the inbox marks an
    activity it defers (IO-03-009), and indexes it under the entry's
    case and ``prev_log_hash``.  An ``Announce`` whose entry is already held
    under the same predecessor is not held again, whatever its id, unless the
    held one lost its body; a different entry under the same predecessor (a
    fork) replaces the held one, with a warning.  Every write, the replaced
    or evicted hold's removal included, commits in one transaction.  When the
    case's holding area is full, the bound applies (SYNC-14-006):
    *max_per_case*, by default :data:`DEFAULT_HELD_LEDGER_ANNOUNCES_MAX`.
    *actor_id*, the receiving actor, names it in the log lines only.

    Returns:
        ``True`` when the entry's ``Announce`` is now held, ``False`` when
        the bound dropped it.

    Raises:
        VultronWiringError: When intake recorded no body for *activity_id*.
    """
    existing = held_successor(dl, entry.case_id, entry.prev_log_hash)
    if existing is not None and existing.entry_hash == entry.entry_hash:
        if holds_held_body(dl, existing):
            logger.debug(
                "held ledger announces: entry '%s' is already held in"
                " Announce '%s' (actor %s); not holding Announce '%s'",
                entry.id_,
                existing.activity_id,
                actor_id,
                activity_id,
            )
            return True
        # The held row lost its body, so it could never replay; this
        # delivery's Announce of the same entry takes its place.
        logger.warning(
            "held ledger announces: held Announce '%s' of entry '%s' has no"
            " held body (actor %s); holding Announce '%s' in its place",
            existing.activity_id,
            entry.id_,
            actor_id,
            activity_id,
        )
    elif existing is not None:
        logger.warning(
            "held ledger announces: replacing forked held entry for case %s"
            " (actor %s) prev_log_hash=%.16s… (old index=%d in '%s', new"
            " index=%d in '%s')",
            entry.case_id,
            actor_id,
            entry.prev_log_hash,
            existing.log_index,
            existing.activity_id,
            entry.log_index,
            activity_id,
        )
    received_body = _received_body(dl, activity_id)
    bound = (
        DEFAULT_HELD_LEDGER_ANNOUNCES_MAX
        if max_per_case is None
        else max_per_case
    )
    # One transaction: a failure part-way leaves the old hold in place and
    # the new one unwritten, never neither.
    with dl.transaction():
        if existing is not None:
            discard_held(dl, existing)
        elif not _make_room(dl, entry, activity_id, bound, actor_id):
            return False
        # A body already owing a replay is the same delivery's; keep it.
        hold_for_replay(dl, activity_id, received_body)
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
        " %s (actor %s, index=%d, prev_log_hash=%.16s…)",
        activity_id,
        entry.id_,
        entry.case_id,
        actor_id,
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
