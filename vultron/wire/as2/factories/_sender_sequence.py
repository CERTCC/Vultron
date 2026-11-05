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

"""The sender's number on a case activity (SYNC-21-001, ADR-0178).

A participant numbers each case activity it sends the CASE_MANAGER that
states a ``ledgerPosition`` (SYNC-18-001), except a ``Read`` or ``Reject``
of a ledger entry, with ``senderSequence``.  This module is the one place
the property is put on an outbound activity (SYNC-21-004):
:func:`stamp_sender_sequence` stamps it.

The wire layer holds no counter and no case roster, so it neither picks
the number nor knows whether the sender is the CASE_MANAGER.  The adapter
that builds the activity asks :func:`sender_sequence_case_ids` which cases
a numbered activity may be about, finds the one its store holds, checks the
activity goes from a participant to that case's CASE_MANAGER, allocates
the number and stamps it here.
"""

from collections.abc import Iterator
from typing import TypeVar

from vultron.errors import VultronActivityConstructionError
from vultron.wire.as2.factories._ledger_position import named_case_ids
from vultron.wire.as2.ledger_reject_envelope import is_genesis_replay_reject
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Read,
    as_Reject,
)

_Activity = TypeVar("_Activity", bound=as_Activity)

_LEDGER_ENTRY_TYPE = "CaseLedgerEntry"


def _names_a_ledger_entry(activity: as_Activity) -> bool:
    """Whether *activity*'s object is a ledger entry, inline or by id.

    A ``Read(CaseLedgerEntry)`` names its entry by reference (SYNC-17-001),
    and an entry's id is ``{case_id}/log/{index}``, so a bare id under one
    of the cases the activity names is an entry's.
    """
    obj = getattr(activity, "object_", None)
    if isinstance(obj, str):
        return any(
            obj.startswith(f"{case_id.rstrip('/')}/log/")
            for case_id in named_case_ids(activity)
        )
    type_ = getattr(obj, "type_", None)
    return type_ is not None and str(type_) == _LEDGER_ENTRY_TYPE


def is_ledger_request(activity: as_Activity) -> bool:
    """Whether *activity* is a ``Read`` or ``Reject`` of a ledger entry.

    The two ask about the ledger and are not case events (CLP-02-013), so
    they carry no number (SYNC-21-001): a request for a missed entry must
    not wait behind the gap it reports.  The objectless genesis-replay
    ``Reject`` is one (SYNC-16-027).
    """
    if not isinstance(activity, (as_Read, as_Reject)):
        return False
    if is_genesis_replay_reject(activity):
        return True
    return _names_a_ledger_entry(activity)


def sender_sequence_case_ids(activity: as_Activity) -> Iterator[str]:
    """The cases a numbered *activity* may be about, in the order to try.

    The cases :func:`named_case_ids` yields, in the order its ledger
    position was found.  Nothing is yielded for an activity that takes no
    number: one already numbered, one that states no ``ledgerPosition``
    (SYNC-18-017), or a ledger request (:func:`is_ledger_request`).
    Whether the sender is a participant writing to the CASE_MANAGER is the
    caller's to check: the wire layer holds no roster.
    """
    if activity.sender_sequence is not None:
        return
    if activity.ledger_position is None or is_ledger_request(activity):
        return
    yield from named_case_ids(activity)


def stamp_sender_sequence(activity: _Activity, number: int) -> _Activity:
    """Return *activity* carrying *number* as its ``senderSequence``.

    *number* is the sender's next number for the case (SYNC-21-002).
    Activities are immutable, so a copy is returned; one already numbered
    is returned unchanged, so a rebuild keeps its first number
    (SYNC-21-003).

    Raises:
        VultronActivityConstructionError: *number* is not a positive
            integer.
    """
    if activity.sender_sequence is not None:
        return activity
    if isinstance(number, bool) or not isinstance(number, int) or number < 1:
        raise VultronActivityConstructionError(
            f"stamp_sender_sequence: {number!r} is not a positive integer"
            " (SYNC-21-002)"
        )
    return activity.model_copy(update={"sender_sequence": number})


__all__ = [
    "is_ledger_request",
    "sender_sequence_case_ids",
    "stamp_sender_sequence",
]
