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

"""The sender's ledger position on a case activity (SYNC-18-001, ADR-0156).

Every activity about a case whose ledger its sender holds states the sender's
ledger tail for that case as ``ledgerPosition``.  This module is the one place
the property is put on an outbound activity (SYNC-18-002): a factory that
takes a position as an argument (the full-case Invite and its replies, the
genesis-replay ``Reject``) passes it to the activity's constructor, and every
other case activity is stamped by :func:`stamp_ledger_position` when the
sender builds it.

The wire layer holds no ledger, so it cannot read the tail itself.  The
adapter that builds the activity asks :func:`ledger_position_case_ids` which
cases the activity names, reads the tail of the first one its store holds,
and stamps it here.  An activity sent before its sender holds the case's
ledger is never stamped, because its store holds no such case.
"""

from collections.abc import Iterator
from typing import TypeVar

from vultron.core.models.ledger_position import LedgerPosition
from vultron.wire.as2.factories._context import case_uri_of
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity

_Activity = TypeVar("_Activity", bound=as_Activity)

#: ``(activity type, object type)`` pairs whose object states its own ledger
#: position, so the activity carries none (SYNC-18-001): a ledger entry names
#: its own index and hash, and a case copy its ``ledgerPosition``
#: (SYNC-16-005).  ``Create(VulnerabilityCase)`` is the creator's first copy
#: and ``Update(VulnerabilityCase)`` the CASE_MANAGER's copy recording a new
#: owner.  ``Join``, ``Ignore``, ``Leave`` and ``Offer`` name the case by typed
#: reference (ADR-0165); they are acts on the case, not copies of it, so they
#: are stamped.
_STATES_ITS_OWN_POSITION: frozenset[tuple[str, str]] = frozenset(
    {
        ("Announce", "CaseLedgerEntry"),
        ("Announce", "VulnerabilityCase"),
        ("Create", "VulnerabilityCase"),
        ("Update", "VulnerabilityCase"),
    }
)


def _type_name(value: object) -> str | None:
    type_ = getattr(value, "type_", None)
    return str(type_) if type_ is not None else None


def object_states_its_own_position(activity: as_Activity) -> bool:
    """Whether *activity*'s object already states a ledger position.

    True for ``Announce(CaseLedgerEntry)``, ``Announce(VulnerabilityCase)``,
    ``Create(VulnerabilityCase)`` and ``Update(VulnerabilityCase)`` with the
    object carried inline.
    """
    obj = getattr(activity, "object_", None)
    pair = (_type_name(activity), _type_name(obj))
    return pair in _STATES_ITS_OWN_POSITION


def _named_cases(activity: as_Activity) -> list[object]:
    """The slots of *activity* that may name its case, most direct first.

    Its ``context``, ``target`` and ``object``, and the ``context`` of its
    object (an ``Add(ParticipantStatus)`` names the case only on the status).
    """
    obj = getattr(activity, "object_", None)
    return [
        activity.context,
        activity.target,
        obj,
        getattr(obj, "context", None),
    ]


def ledger_position_case_ids(activity: as_Activity) -> Iterator[str]:
    """The cases *activity* may be about, in the order to try them.

    The slots :func:`_named_cases` lists, then those of the activity it
    answers (an ``Accept`` or ``Reject`` carries the activity inline).  Each
    is reduced to the case URI it names (:func:`case_uri_of`); a value that
    names something other than a case is yielded too, and the caller skips
    it because its store holds no case under that id.  Nothing is yielded
    for an activity that needs no position: one already stamped, or one
    whose object states its own (:func:`object_states_its_own_position`).
    """
    if activity.ledger_position is not None:
        return
    if object_states_its_own_position(activity):
        return
    sources = _named_cases(activity)
    obj = getattr(activity, "object_", None)
    if isinstance(obj, as_Activity):
        sources += _named_cases(obj)
    seen: set[str] = set()
    for source in sources:
        if source is None:
            continue
        case_id = case_uri_of(source)
        if case_id is not None and case_id not in seen:
            seen.add(case_id)
            yield case_id


def stamp_ledger_position(
    activity: _Activity, position: LedgerPosition
) -> _Activity:
    """Return *activity* stating *position* as its ``ledgerPosition``.

    *position* is the sender's ledger tail for the case when it builds the
    activity (SYNC-18-001, SYNC-18-002).  Activities are immutable, so a
    copy is returned; an activity that already states a position is
    returned unchanged, so a resend keeps its first stamp.
    """
    if activity.ledger_position is not None:
        return activity
    return activity.model_copy(update={"ledger_position": position})


__all__ = [
    "ledger_position_case_ids",
    "object_states_its_own_position",
    "stamp_ledger_position",
]
