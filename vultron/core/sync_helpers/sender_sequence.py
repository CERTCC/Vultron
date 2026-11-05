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

"""The sender's side of the sender sequence (SYNC-21, ADR-0178).

A participant numbers each case activity it sends the CASE_MANAGER: 1 for
its first on a case, one more than the last after that (SYNC-21-002).  The
last number used is a :class:`SenderSequenceCounter` in the sender's own
DataLayer (SYNC-21-020).

:func:`allocate_sender_sequence` hands out the next number.  It is never
lower than one past the highest of the sender's own numbers in the case
ledger it holds, so a sender that lost its counter resumes past every
number the ledger records (SYNC-21-006).  The caller allocates inside the
transaction that seals the activity's body, so a number is used once:
a body that is never sealed gives its number back, and a sealed one keeps
it for every resend (SYNC-21-003).

:func:`resume_sender_sequence_at` moves the counter up to a number the
CASE_MANAGER names in a refusal notice, so the sender's next activity is
numbered no lower (SYNC-21-007).  It never moves the counter down.
"""

import logging

from vultron.core.models.activity import VultronActivity
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.sender_sequence import (
    SenderSequenceCounter,
    is_sender_sequence,
)
from vultron.core.models.wire_keys import wire_key
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.predicates.addressing import snapshot_actor_id
from vultron.core.sync_helpers.ledger_reads import sorted_case_ledger_entries
from vultron.primitives import normalise_actor_id

logger = logging.getLogger(__name__)

#: The wire name of the number on an activity's body (SYNC-21-001).
SENDER_SEQUENCE_KEY = wire_key("sender_sequence", VultronActivity)


def _stated_number(entry: CaseLedgerEntry) -> int | None:
    """The positive ``senderSequence`` *entry*'s received body states."""
    number = entry.payload_snapshot.get(SENDER_SEQUENCE_KEY)
    return number if is_sender_sequence(number) else None


def highest_ledgered_sender_sequence(
    dl: CasePersistence, case_id: str, sender_id: str
) -> int:
    """The highest ``senderSequence`` of *sender_id*'s in *case_id*'s ledger.

    An admitted activity keeps its number in its entry's received body
    (SYNC-21-005), so the ledger *dl* holds says how far the sender has got
    (SYNC-21-006).  0 when the ledger records none of its numbers.
    """
    sender = normalise_actor_id(sender_id)
    highest = 0
    for entry in sorted_case_ledger_entries(dl, case_id):
        if snapshot_actor_id(entry.payload_snapshot.get("actor")) != sender:
            continue
        number = _stated_number(entry)
        if number is not None and number > highest:
            highest = number
    return highest


def _read_counter(
    dl: CasePersistence, case_id: str, sender_id: str
) -> SenderSequenceCounter:
    stored = dl.read(SenderSequenceCounter.build_id(case_id, sender_id))
    if isinstance(stored, SenderSequenceCounter):
        return stored
    return SenderSequenceCounter(case_id=case_id, sender_id=sender_id)


def _save_counter(
    dl: CasePersistence, case_id: str, sender_id: str, last_used: int
) -> None:
    """Store the counter at *last_used*, validated as built (CM-27-001)."""
    dl.save(
        SenderSequenceCounter(
            case_id=case_id, sender_id=sender_id, last_used=last_used
        )
    )


def allocate_sender_sequence(
    dl: CasePersistence, case_id: str, sender_id: str
) -> int:
    """Use and return *sender_id*'s next ``senderSequence`` for *case_id*.

    One more than the higher of the stored counter and the sender's highest
    number in the ledger *dl* holds (SYNC-21-002, SYNC-21-006).  The counter
    is saved at the number returned, in a transaction of its own; call this
    inside the transaction that seals the numbered activity too, so a body
    never sealed gives its number back (SYNC-21-003, SYNC-21-020).
    """
    with dl.transaction():
        counter = _read_counter(dl, case_id, sender_id)
        ledgered = highest_ledgered_sender_sequence(dl, case_id, sender_id)
        if ledgered > counter.last_used:
            logger.info(
                "Sender '%s' resumes its sender sequence for case '%s' past %d,"
                " the highest of its numbers the ledger records (its counter"
                " was at %d) (SYNC-21-006)",
                sender_id,
                case_id,
                ledgered,
                counter.last_used,
            )
        number = max(counter.last_used, ledgered) + 1
        _save_counter(dl, case_id, sender_id, number)
        return number


def resume_sender_sequence_at(
    dl: CasePersistence, case_id: str, sender_id: str, expected: int
) -> bool:
    """Make *sender_id*'s next number for *case_id* at least *expected*.

    *expected* is the ``expectedSenderSequence`` of a refusal notice from the
    case's CASE_MANAGER (SYNC-21-007).  The counter moves up to one below
    it; one already there or past it is left alone, so a stale notice never
    makes the sender reuse a number.

    Returns:
        Whether the counter moved.
    """
    floor = expected - 1
    # Read and save as one, so a number allocated meanwhile is never
    # overwritten by a lower floor.
    with dl.transaction():
        counter = _read_counter(dl, case_id, sender_id)
        if counter.last_used >= floor:
            return False
        _save_counter(dl, case_id, sender_id, floor)
        return True


__all__ = [
    "SENDER_SEQUENCE_KEY",
    "allocate_sender_sequence",
    "highest_ledgered_sender_sequence",
    "resume_sender_sequence_at",
]
