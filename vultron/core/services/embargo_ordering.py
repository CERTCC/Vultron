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

"""The one comparator for competing embargo terms (EP-08, EP-04-003, ADR-0100).

"Shortest embargo proposed wins": among open proposals the one whose embargo
ends earliest is taken first; at case creation the shorter of the sender's
proposal and the actor default becomes active.  Both are the same rule on
different inputs, and EP-08-001 requires them to share one implementation so
they cannot disagree.  :func:`earliest_ending` is that implementation;
:func:`earliest_expiring_embargo_id` applies it to stored ``EmbargoEvent``
records for callers that hold ids rather than objects.
"""

from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, TypeVar

from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.datalayer import DataLayer
from vultron.errors import VultronNotFoundError, VultronValidationError

if TYPE_CHECKING:
    from _typeshed import SupportsRichComparison

T = TypeVar("T")
K = TypeVar("K", bound="SupportsRichComparison")


def earliest_ending(candidates: Iterable[T], *, end: Callable[[T], K]) -> T:
    """Return the candidate whose *end* is earliest; ties keep the first seen.

    *end* may yield an instant (``datetime``) or a length (``timedelta``)
    measured from a common start — either way the smallest wins.  A tie keeps
    the earlier candidate in iteration order, so a caller that lists the
    sender's terms before the receiver's resolves an exact tie to the sender.

    Raises:
        ValueError: If *candidates* is empty — the caller decides what "no
            candidate" means (EP-04-005's protocol default, or "nothing to
            select"), never this function.
    """
    items = list(candidates)
    if not items:
        raise ValueError("earliest_ending: no candidates")
    return min(items, key=end)


def earliest_expiring_embargo_id(
    store: CasePersistence, embargo_ids: Iterable[str]
) -> str:
    """Return the id in *embargo_ids* whose stored ``EmbargoEvent`` ends first.

    Every id MUST resolve to an ``EmbargoEvent``: a candidate that cannot be
    ordered neither silently wins nor silently vanishes (EP-08-002), because
    either would reproduce the arrival-order defect under a different name.
    (``EmbargoEvent.end_time`` is required, #3404, so a resolved record can
    always be ordered.)

    Two records that end at the same instant are indistinguishable in the
    dimension EP-08 orders on, so the tie keeps the first id in *embargo_ids*
    — which, for callers passing a case's open proposals, is recording order.
    That is the one place position may decide, and only between equals.

    Raises:
        VultronNotFoundError: If an id does not resolve in *store*.
        VultronValidationError: If a record is not an ``EmbargoEvent``.
        ValueError: If *embargo_ids* is empty.
    """
    events = [
        read_embargo_event(store, embargo_id) for embargo_id in embargo_ids
    ]
    return earliest_ending(events, end=lambda e: e.end_time).id_


def read_embargo_event(
    store: CasePersistence | DataLayer, embargo_id: str
) -> EmbargoEvent:
    """Read the stored ``EmbargoEvent`` *embargo_id*, failing closed.

    The one embargo read path of the comparator and of the activation
    writers (EMB-18-003): an id that does not resolve, or resolves to
    something other than an ``EmbargoEvent``, raises rather than reading as
    absent.

    Raises:
        VultronNotFoundError: If *embargo_id* does not resolve in *store*.
        VultronValidationError: If the record is not an ``EmbargoEvent``.
    """
    record = store.read(embargo_id)
    if record is None:
        raise VultronNotFoundError("EmbargoEvent", embargo_id)
    if not isinstance(record, EmbargoEvent):
        raise VultronValidationError(
            f"Embargo '{embargo_id}' is not an"
            f" EmbargoEvent (got {type(record).__name__})."
        )
    return record


__all__ = [
    "earliest_ending",
    "earliest_expiring_embargo_id",
    "read_embargo_event",
]
