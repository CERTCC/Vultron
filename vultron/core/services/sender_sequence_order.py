#!/usr/bin/env python

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

"""The CASE_MANAGER's side of the sender sequence (SYNC-21, ADR-0178).

The CASE_MANAGER judges each sender's numbered activities for a case in
``senderSequence`` order (SYNC-21-008).  Per (sender, case) it keeps a
:class:`~vultron.core.models.sender_sequence.SenderSequenceOrder`: the number
it judges next, and the activities it holds past a gap (SYNC-21-009,
SYNC-21-010, SYNC-21-020).

- :func:`sender_sequence_order` reads that record, or starts one from the
  highest of the sender's numbers in the case ledger the CASE_MANAGER holds,
  so a new CASE_MANAGER starts where the ledger is (SYNC-21-009).
- :func:`classify_sender_sequence` says what a received number is: next, past
  a gap, a repeat, late, reused or missing.  It reads nothing and writes
  nothing.
- :func:`admit_in_order` moves the next expected number past an activity
  about to be judged; :func:`hold_past_gap` holds one past a gap, and ends
  the hold when the sender reaches the cap or the wait has passed
  (SYNC-21-011, SYNC-21-012).
- An ended hold sets ``skip_through`` to its highest number: every activity
  held up to it is then judged in number order, and the numbers still
  missing before each are skipped, each logged at WARNING (SYNC-21-013,
  SYNC-21-022).  :func:`end_expired_sender_sequence_holds` ends the holds
  whose wait has passed, whether or not anything else arrives, and
  :func:`end_case_sender_sequence_holds` ends every hold for a case before
  the CASE_MANAGER role passes (SYNC-21-025).

What is due for a replay is read from the record, never kept in a second
list: a held activity is due once its number is the next expected one, or
it lies within an ended hold.  :func:`queue_due_sender_sequence_replays`
hands each due activity to the inbox's replay port, which replays the body
that arrived as a delivery of its own (IO-03-009, ADR-0154), so the tree
judges it unchanged.  The inbox calls it after every dispatch; the held
bodies' own judging is never run inside the delivery that made them due.
"""

import logging
from collections.abc import Iterable
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Final

from vultron.core.models.sender_sequence import (
    HeldSenderActivity,
    SenderSequenceOrder,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.inbox_replay import InboxReplayPort
from vultron.core.services.received_holding import hold_unjudged_for_replay
from vultron.core.sync_helpers.sender_sequence import (
    highest_ledgered_sender_sequence,
)
from vultron.primitives import same_actor_id

logger = logging.getLogger(__name__)

_ORDER_TYPE: Final = "SenderSequenceOrder"


class SequenceStanding(StrEnum):
    """What a received activity's ``senderSequence`` is to the CASE_MANAGER."""

    NOT_NUMBERED = "not-numbered"
    """The activity takes no number (SYNC-21-001): judged as it is."""
    NEXT = "next"
    """The number the CASE_MANAGER expects next: judged now."""
    PAST_SKIP = "past-skip"
    """A number within an ended hold: the gap before it is skipped and it is
    judged now (SYNC-21-013)."""
    AHEAD = "ahead"
    """Past a gap: held until the gap fills or the hold ends (SYNC-21-010)."""
    HELD_REPEAT = "held-repeat"
    """A repeat of an activity the CASE_MANAGER holds: the held copy stays,
    and nothing is sent (SYNC-21-018)."""
    JUDGED_REPEAT = "judged-repeat"
    """A repeat of an activity already judged in order, which the tree
    answers as any repeat (ID-02-001, ADR-0151)."""
    REPEAT_REFUSED = "repeat-refused"
    """A repeat of an activity refused for its number (late, reused or
    missing), or judged before a later one: refused again, with no notice
    (CLP-05-006, SYNC-21-024)."""
    LATE = "late"
    """Below the next expected number: refused with a notice (SYNC-21-014)."""
    REUSED = "reused"
    """The number of an activity the CASE_MANAGER holds, on another activity:
    refused with a notice (SYNC-21-014)."""
    MISSING = "missing"
    """No number, or one that is not a positive integer, where one is
    required: refused with a notice (SYNC-21-017)."""


#: The standings whose activity the tree goes on to judge.
JUDGED: Final = frozenset(
    {
        SequenceStanding.NOT_NUMBERED,
        SequenceStanding.NEXT,
        SequenceStanding.PAST_SKIP,
        SequenceStanding.JUDGED_REPEAT,
    }
)

#: The standings refused with a notice naming the next expected number
#: (SYNC-21-015).
NOTICED: Final = frozenset(
    {SequenceStanding.LATE, SequenceStanding.REUSED, SequenceStanding.MISSING}
)


def sender_sequence_order(
    dl: CasePersistence, case_id: str, sender_id: str
) -> SenderSequenceOrder:
    """The CASE_MANAGER's order record for *sender_id* on *case_id*.

    The stored record, or, before the CASE_MANAGER has judged any of the
    sender's numbers, one starting at one more than the highest of them its
    case ledger records, and at 1 when it records none (SYNC-21-009).  A
    started record is not saved until something changes it.
    """
    stored = dl.read(SenderSequenceOrder.build_id(case_id, sender_id))
    if isinstance(stored, SenderSequenceOrder):
        return stored
    return SenderSequenceOrder(
        case_id=case_id,
        sender_id=sender_id,
        next_expected=highest_ledgered_sender_sequence(dl, case_id, sender_id)
        + 1,
    )


def _held_by_id(
    order: SenderSequenceOrder, activity_id: str
) -> HeldSenderActivity | None:
    return next(
        (held for held in order.held if held.activity_id == activity_id), None
    )


def classify_sender_sequence(
    order: SenderSequenceOrder,
    number: int | None,
    activity_id: str,
    *,
    redelivery: bool,
    ledgered: bool,
) -> SequenceStanding:
    """What *number* on *activity_id* is to *order* (SYNC-21-008 to -018).

    A repeat is found by its id before its number is compared
    (SYNC-21-018): one held is a held repeat; one this receiver archived
    before (*redelivery*) whose number is past is a judged repeat when the
    ledger records it (*ledgered*) or it is the activity last judged in
    order, and is otherwise refused again with no notice, so a late activity
    is never applied however it arrives (SYNC-21-024).  A repeat of one
    refused for a missing or reused number is refused again with no notice
    too: the first refusal's notice answered it (CLP-05-006).

    Args:
        order: The sender's order record.
        number: The activity's ``senderSequence``; ``None`` when it carries
            none or one that is not a positive integer.
        activity_id: The activity's id.
        redelivery: Whether this receiver had already archived the activity.
        ledgered: Whether the case ledger records the activity.
    """
    if number is not None and _held_by_id(order, activity_id) is not None:
        return SequenceStanding.HELD_REPEAT
    reused = any(held.number == number for held in order.held)
    if redelivery and (number is None or reused):
        # Refused for its number when it first came, with the notice that
        # answered it; a repeat is not answered again (CLP-05-006).
        return SequenceStanding.REPEAT_REFUSED
    if number is None:
        return SequenceStanding.MISSING
    if reused:
        return SequenceStanding.REUSED
    if number < order.next_expected:
        if not redelivery:
            return SequenceStanding.LATE
        if ledgered or activity_id == order.last_judged_id:
            return SequenceStanding.JUDGED_REPEAT
        return SequenceStanding.REPEAT_REFUSED
    if number == order.next_expected:
        return SequenceStanding.NEXT
    if number <= order.skip_through:
        return SequenceStanding.PAST_SKIP
    return SequenceStanding.AHEAD


def _save(
    dl: CasePersistence,
    order: SenderSequenceOrder,
    *,
    next_expected: int | None = None,
    skip_through: int | None = None,
    last_judged_id: str | None = None,
    held: Iterable[HeldSenderActivity] | None = None,
) -> SenderSequenceOrder:
    """Store *order* with the given changes, validated as built (CM-27-001)."""
    expected = order.next_expected if next_expected is None else next_expected
    through = order.skip_through if skip_through is None else skip_through
    updated = SenderSequenceOrder(
        case_id=order.case_id,
        sender_id=order.sender_id,
        next_expected=expected,
        # An ended hold is done once every number in it is past.
        skip_through=through if through >= expected else 0,
        last_judged_id=(
            order.last_judged_id if last_judged_id is None else last_judged_id
        ),
        held=sorted(
            order.held if held is None else held, key=lambda h: h.number
        ),
    )
    dl.save(updated)
    return updated


def admit_in_order(
    dl: CasePersistence,
    order: SenderSequenceOrder,
    number: int,
    activity_id: str,
) -> SenderSequenceOrder:
    """Move the next expected number past *number*, about to be judged.

    The activity counts as judged whatever its merits decide, so a refusal
    on its merits moves the number on too (SYNC-21-009).  Each number still
    missing below it, within an ended hold, is skipped and logged at WARNING
    with the sender and the case (SYNC-21-013, SYNC-21-022).
    """
    for skipped in range(order.next_expected, number):
        logger.warning(
            "Sender sequence: skipped number %d from sender '%s' on case"
            " '%s'; its hold ended before it arrived (SYNC-21-013,"
            " SYNC-21-022)",
            skipped,
            order.sender_id,
            order.case_id,
        )
    return _save(
        dl,
        order,
        next_expected=number + 1,
        last_judged_id=activity_id,
        held=[h for h in order.held if h.activity_id != activity_id],
    )


def _hold_has_ended(
    order: SenderSequenceOrder, now: datetime, *, cap: int, wait: timedelta
) -> bool:
    if not order.held:
        return False
    if len(order.held) >= cap:
        return True
    return min(h.held_at for h in order.held) + wait <= now


def _ended(order: SenderSequenceOrder, why: str) -> int:
    """The ``skip_through`` that ends *order*'s hold; logs why it ended."""
    through = max(h.number for h in order.held)
    logger.info(
        "Sender sequence: hold of %d activities from sender '%s' on case"
        " '%s' ended (%s); judging them in number order through %d, with"
        " number %d still expected (SYNC-21-013)",
        len(order.held),
        order.sender_id,
        order.case_id,
        why,
        through,
        order.next_expected,
    )
    return through


def hold_past_gap(
    dl: CasePersistence,
    order: SenderSequenceOrder,
    number: int,
    activity_id: str,
    now: datetime,
    *,
    cap: int,
    wait: timedelta,
) -> SenderSequenceOrder:
    """Hold *activity_id*, numbered past a gap, as the body that arrived.

    The body goes back to holding on its one received record (IO-03-009),
    and the record of the order gains it (SYNC-21-010).  When the sender's
    held activities reach *cap*, or the oldest of them has waited *wait*,
    the hold ends (SYNC-21-011, SYNC-21-012), and the held activities become
    due for their replay in number order.  Write it in one transaction.
    """
    with dl.transaction():
        hold_unjudged_for_replay(dl, activity_id)
        held = HeldSenderActivity(
            number=number, activity_id=activity_id, held_at=now
        )
        grown = order.model_copy(update={"held": [*order.held, held]})
        logger.info(
            "Sender sequence: holding activity '%s' numbered %d from sender"
            " '%s' on case '%s' until number %d arrives (SYNC-21-010)",
            activity_id,
            number,
            order.sender_id,
            order.case_id,
            order.next_expected,
        )
        through: int | None = None
        if len(grown.held) >= cap:
            through = _ended(grown, f"the cap of {cap} is reached")
        elif _hold_has_ended(grown, now, cap=cap, wait=wait):
            through = _ended(grown, "its wait has passed")
        return _save(dl, order, skip_through=through, held=grown.held)


def _orders(dl: CasePersistence) -> list[SenderSequenceOrder]:
    return [
        obj
        for obj in dl.list_objects(_ORDER_TYPE)
        if isinstance(obj, SenderSequenceOrder)
    ]


def end_expired_sender_sequence_holds(
    dl: CasePersistence, now: datetime, wait: timedelta
) -> int:
    """End every hold whose oldest activity has waited *wait* by *now*.

    The hold ends whether or not anything else arrives (SYNC-21-011); its
    activities are then due for their replay (SYNC-21-013).  Returns how many
    holds ended.
    """
    ended = 0
    for order in _orders(dl):
        if not order.held or order.skip_through >= max(
            h.number for h in order.held
        ):
            continue
        if min(h.held_at for h in order.held) + wait > now:
            continue
        _save(dl, order, skip_through=_ended(order, "its wait has passed"))
        ended += 1
    return ended


def end_case_sender_sequence_holds(dl: CasePersistence, case_id: str) -> int:
    """End every hold for *case_id*, before the CASE_MANAGER role passes.

    Each sender's held activities are then judged in number order, skipping
    the gaps, exactly as when a wait ends (SYNC-21-025), so the outgoing
    CASE_MANAGER keeps nothing held and sends no notice for any of them.
    Returns how many holds ended.
    """
    ended = 0
    for order in _orders(dl):
        if order.case_id != case_id or not order.held:
            continue
        _save(
            dl,
            order,
            skip_through=_ended(order, "the CASE_MANAGER role passes"),
        )
        ended += 1
    return ended


def due_for_replay(order: SenderSequenceOrder) -> list[HeldSenderActivity]:
    """The held activities of *order* to judge now, in number order.

    The one numbered next, and every one within an ended hold
    (SYNC-21-013).
    """
    limit = max(order.next_expected, order.skip_through)
    return [h for h in order.held if h.number <= limit]


def queue_due_sender_sequence_replays(
    dl: CasePersistence,
    replay: InboxReplayPort,
    *,
    sender_id: str | None = None,
) -> int:
    """Queue every held activity now due for its replay, in number order.

    Each is replayed through the inbox as a delivery of its own, the body
    that arrived (IO-03-009, ADR-0154), and leaves the record of the order
    in the same transaction as it is queued, so a failure leaves it held.
    With *sender_id*, only that sender's records are read.  Returns how many
    were queued.
    """
    queued = 0
    for order in _orders(dl):
        if sender_id is not None and not same_actor_id(
            order.sender_id, sender_id
        ):
            continue
        due = due_for_replay(order)
        if not due:
            continue
        with dl.transaction():
            for held in due:
                replay.replay_held(held.activity_id)
            _save(
                dl,
                order,
                held=[h for h in order.held if h not in due],
            )
        for held in due:
            logger.info(
                "Sender sequence: replaying held activity '%s' numbered %d"
                " from sender '%s' on case '%s' (SYNC-21-008)",
                held.activity_id,
                held.number,
                order.sender_id,
                order.case_id,
            )
        queued += len(due)
    return queued


__all__ = [
    "JUDGED",
    "NOTICED",
    "SequenceStanding",
    "admit_in_order",
    "classify_sender_sequence",
    "due_for_replay",
    "end_case_sender_sequence_holds",
    "end_expired_sender_sequence_holds",
    "hold_past_gap",
    "queue_due_sender_sequence_replays",
    "sender_sequence_order",
]
