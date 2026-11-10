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

"""Whether an embargo an ``Accept`` names is still available (MSM-07-012).

The answer to an ``Accept(Invite(EmbargoEvent))`` depends on the embargo it
names, never on whether it arrived before its RSVP deadline (EMB-17-001).
:func:`embargo_availability` is the one test, read on the on-time and the
late path alike:

- **available** — the case's Active Embargo or one of its open proposals
  (:meth:`~vultron.core.models.case.VulnerabilityCase.can_answer_embargo`),
  whose end time has not passed: the Accept is honoured;
- **unavailable** — the register holds it, but it was replaced, rejected,
  cancelled or terminated, or it has reached its end time: the Accept is
  refused (MSM-07-012);
- **never held** — the register has no entry for it: the Accept is not
  understood (MSM-07-039, MSM-05-001).

:func:`available_terms` names the terms a refused accepter is re-invited to
(EMB-17-003), by the same test, so the refusal and the re-invite cannot
disagree on what is available.
"""

from datetime import datetime
from enum import StrEnum

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.embargo_termination import has_reached_end_time
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.embargo_ordering import (
    earliest_ending,
    read_embargo_event,
)
from vultron.errors import VultronNotAnEmbargoError, VultronNotFoundError

__all__ = [
    "EmbargoAvailability",
    "available_terms",
    "embargo_availability",
    "embargo_end_time",
]


class EmbargoAvailability(StrEnum):
    """What an ``Accept`` of an embargo can still do (MSM-07-012)."""

    AVAILABLE = "available"
    """The Active Embargo or an open proposal, before its end time."""

    UNAVAILABLE = "unavailable"
    """Held by the register, but final or past its end time."""

    NEVER_HELD = "never_held"
    """The register has no entry for it."""


def _stored_embargo(
    store: CasePersistence, case: VulnerabilityCase, embargo_id: str
) -> EmbargoEvent:
    """The ``EmbargoEvent`` *embargo_id*: the register's copy, else the store's.

    Raises:
        RuntimeError: The register names *embargo_id* but neither carries the
            object nor finds it in *store*.  The CASE_MANAGER holds its own
            case, so that is a fault in its own store, never the sender's
            (Regime 1, ADR-0087; EMB-18-003).
    """
    entry = case.embargo_register_entry(embargo_id)
    if entry is not None and isinstance(entry.embargo, EmbargoEvent):
        return entry.embargo
    try:
        return read_embargo_event(store, embargo_id)
    except (VultronNotFoundError, VultronNotAnEmbargoError) as exc:
        raise RuntimeError(
            f"case '{case.id_}' holds embargo '{embargo_id}' in its register,"
            f" but its CASE_MANAGER's store cannot read it: {exc}"
        ) from exc


def embargo_end_time(
    store: CasePersistence, case: VulnerabilityCase, embargo_id: str
) -> datetime:
    """The end time of *embargo_id*, an embargo *case*'s register holds.

    Raises:
        RuntimeError: The embargo cannot be read (see :func:`_stored_embargo`).
    """
    return _stored_embargo(store, case, embargo_id).end_time


def embargo_availability(
    store: CasePersistence,
    case: VulnerabilityCase,
    embargo_id: str,
    now: datetime,
) -> EmbargoAvailability:
    """Whether *case* can still take an ``Accept`` of *embargo_id* at *now*.

    The register status comes first (CM-18-003): only the Active Embargo
    and the open proposals take an answer.  Of those, one whose embargo has
    reached its end time is no longer available either: an ``ACTIVE`` entry
    the clock has not yet terminated, or a ``PROPOSED`` entry nobody has
    decided (EMB-13-003, EP-07-006).  An embargo reaches its end time at
    that instant (:func:`~vultron.core.models.embargo_termination.has_reached_end_time`).

    Raises:
        RuntimeError: An answerable embargo cannot be read from *store*.
    """
    if case.embargo_register_entry(embargo_id) is None:
        return EmbargoAvailability.NEVER_HELD
    if not case.can_answer_embargo(embargo_id):
        return EmbargoAvailability.UNAVAILABLE
    if has_reached_end_time(embargo_end_time(store, case, embargo_id), now):
        return EmbargoAvailability.UNAVAILABLE
    return EmbargoAvailability.AVAILABLE


def available_terms(
    store: CasePersistence, case: VulnerabilityCase, now: datetime
) -> str | None:
    """The embargo a refused accepter is re-invited to, or ``None`` (EMB-17-003).

    The case's Active Embargo when it is available; otherwise the
    earliest-ending available open proposal, chosen by the shared comparator
    (EP-08-002).  An embargo past its end time is no terms: an Invite to it
    could carry no RSVP deadline the protocol allows (EP-07-002, EP-07-006).
    ``None`` when the case holds no available embargo: there is nothing to
    invite to (EMB-17-004, EMB-17-007).

    Raises:
        RuntimeError: An answerable embargo cannot be read from *store*.
    """

    def available(embargo_id: str) -> bool:
        return (
            embargo_availability(store, case, embargo_id, now)
            is EmbargoAvailability.AVAILABLE
        )

    active_id = case.active_embargo_id
    if active_id is not None and available(active_id):
        return active_id
    live = [
        _stored_embargo(store, case, embargo_id)
        for embargo_id in case.proposed_embargo_ids
        if available(embargo_id)
    ]
    if not live:
        return None
    return earliest_ending(live, end=lambda e: e.end_time).id_
