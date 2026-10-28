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

"""Object dereference: which references a receiver fetches, and the read it
serves (AKM-05-003, AKM-05-006, AKM-05-007, ADR-0107).

Two sides of one exchange live here, both pure core:

- :func:`references_to_fetch` decides, for one received event, which objects
  the receiver must fetch before the event can be processed, and from whom.
  The inbox defers the activity on them and replays it once each fetch
  settles; :func:`with_fetched_object` hands a fetched object that is never
  stored to the event that waited on it.
- :func:`case_object_for_participant` is the case host's read: an object the
  case names, to an active participant of that case.

Nothing here fetches.  The fetch is an adapter's HTTP call; core only names
the object and its source.
"""

from __future__ import annotations

import logging

from vultron.core.models.actor import CoreActor
from vultron.core.models.base import CoreObject
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.events import MessageSemantics, VultronEvent
from vultron.core.models.events.case_proposal import (
    CreateCaseProposalReceivedEvent,
)
from vultron.core.models.events.embargo import (
    AnnounceEmbargoEventToCaseReceivedEvent,
)
from vultron.core.models.object_fetch import (
    ObjectFetchSource,
    ObjectFetchUse,
    ObjectReference,
)
from vultron.core.models.protocols import PersistableModel
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.participants.recipients import may_act_on_case
from vultron.core.ports.case_persistence import CasePersistence
from vultron.errors import (
    VultronNotACaseParticipantError,
    VultronNotFoundError,
    VultronValidationError,
)
from vultron.primitives import normalise_actor_id, same_actor_id

logger = logging.getLogger(__name__)


def _id_of(value: object) -> str | None:
    """The id of a reference slot's value: the IRI itself, or the object's."""
    if isinstance(value, str):
        return value or None
    found = getattr(value, "id_", None)
    return found if isinstance(found, str) and found else None


def _is_ledger_entry_id(case_id: str, object_id: str) -> bool:
    """True when *object_id* names one of *case_id*'s ledger entries.

    A ledger entry's id is ``{case_id}/log/{index}`` (``CaseLedgerEntry``).
    """
    return object_id.startswith(f"{case_id.rstrip('/')}/log/")


def _case_host_of(
    dl: CasePersistence, case_id: str | None, receiving_actor_id: str
) -> tuple[VulnerabilityCase, str] | None:
    """The held case and its CASE_MANAGER, when the receiver can fetch from it.

    ``None`` when the receiver holds no such case, the case names no
    CASE_MANAGER, or the receiver is the CASE_MANAGER itself: the case host
    holds the canonical case, so nobody else has an object it lacks
    (AKM-05-007).
    """
    if case_id is None:
        return None
    case = dl.read_case(case_id)
    if case is None:
        return None
    manager_id = resolve_case_manager_id(case, dl)
    if manager_id is None or same_actor_id(manager_id, receiving_actor_id):
        return None
    return case, manager_id


def _case_host_reference(
    object_id: str, case: VulnerabilityCase, manager_id: str
) -> ObjectReference:
    return ObjectReference(
        object_id=object_id,
        source=ObjectFetchSource.CASE_HOST,
        host_actor_id=manager_id,
        case_id=case.id_,
        use=ObjectFetchUse.STORE,
    )


def _unresolvable_object_references(
    event: VultronEvent,
    dl: CasePersistence,
    receiving_actor_id: str,
    context_id: str | None,
) -> list[ObjectReference]:
    """The bare ``object`` of an activity no pattern could match.

    The activity's type has patterns, but its ``object`` stayed a bare id
    because the receiver does not hold it (``UNKNOWN_UNRESOLVABLE_OBJECT``).
    When the ``object`` is an inline activity, the bare id is that
    activity's own object, the event's ``inner_object`` (VAM-01-009).
    A replication ``Announce`` of a ledger entry is never fetched: it carries
    its entry inline (SYNC-02-005), and replay needs no fetch (AKM-05-007).
    """
    object_id = event.inner_object_id or event.object_id
    if object_id is None or dl.read(object_id) is not None:
        return []
    host = _case_host_of(dl, context_id, receiving_actor_id)
    if host is None:
        return []
    case, manager_id = host
    if _is_ledger_entry_id(case.id_, object_id):
        return []
    return [_case_host_reference(object_id, case, manager_id)]


def _proposer_profile_references(
    event: CreateCaseProposalReceivedEvent,
) -> list[ObjectReference]:
    """The proposer's profile, when the proposal names it by reference.

    The profile is read from the proposer, never from the receiver's store,
    and is handed to this proposal alone (CP-01-009, CP-01-010).
    """
    profile = event.proposer_profile
    if not isinstance(profile, str):
        return []
    return [
        ObjectReference(
            object_id=profile,
            source=ObjectFetchSource.ACTOR_PROFILE,
            host_actor_id=profile,
            use=ObjectFetchUse.HAND_OFF,
        )
    ]


def _replaced_embargo_references(
    event: AnnounceEmbargoEventToCaseReceivedEvent,
    dl: CasePersistence,
    receiving_actor_id: str,
) -> list[ObjectReference]:
    """The replica's own active embargo, when the replica cannot read it.

    Applying an announced revision compares it with the embargo it replaces
    (EP-05-001, CM-31-010), so a replica fetches a replaced embargo it does
    not hold from the case host before it applies the revision; only a
    failed fetch refuses (EMB-18-007).
    """
    host = _case_host_of(dl, event.case_id, receiving_actor_id)
    if host is None:
        return []
    case, manager_id = host
    replaced_id = case.active_embargo_id
    if replaced_id is None or replaced_id == event.embargo_id:
        return []
    if dl.read(replaced_id) is not None:
        return []
    return [_case_host_reference(replaced_id, case, manager_id)]


def references_to_fetch(
    event: VultronEvent,
    dl: CasePersistence,
    receiving_actor_id: str,
    context_id: str | None = None,
) -> list[ObjectReference]:
    """The objects *event* names that the receiver must fetch first.

    Empty when the receiver holds everything the event needs, or when no one
    the receiver could ask holds more than it does.  The receiver never asks
    itself: a CASE_MANAGER lacking a case object has no one to fetch it from,
    so its existing refusal stands (AKM-05-011, EMB-18-003).

    Args:
        event: The extracted received event.
        dl: The receiving actor's store.
        receiving_actor_id: The receiving actor.
        context_id: The case the inbox resolved the activity to, if any.
    """
    if isinstance(event, CreateCaseProposalReceivedEvent):
        return _proposer_profile_references(event)
    if isinstance(event, AnnounceEmbargoEventToCaseReceivedEvent):
        return _replaced_embargo_references(event, dl, receiving_actor_id)
    if event.semantic_type is MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT:
        return _unresolvable_object_references(
            event, dl, receiving_actor_id, context_id
        )
    return []


def with_fetched_object(
    event: VultronEvent, reference: ObjectReference, fetched: CoreObject
) -> VultronEvent:
    """Return *event* carrying the handed-off object *fetched* for *reference*.

    Only a :attr:`ObjectFetchUse.HAND_OFF` reference is handed off: the
    proposer's profile, which becomes the proposal's inline profile for this
    proposal and no other (CP-01-010).  The received body is untouched; the
    event is the receiver's reading of it.

    Raises:
        VultronValidationError: When *fetched* is not what *reference* names,
            or *event* has no slot for it.
    """
    if not same_actor_id(fetched.id_, reference.object_id):
        raise VultronValidationError(
            f"the fetched object {fetched.id_!r} is not the"
            f" {reference.object_id!r} the activity names"
        )
    if isinstance(event, CreateCaseProposalReceivedEvent) and isinstance(
        event.proposer_profile, str
    ):
        if not isinstance(fetched, CoreActor) or type(fetched) is CoreActor:
            raise VultronValidationError(
                f"the fetched {reference.object_id!r} is a"
                f" {type(fetched).__name__}, not an actor profile"
                " (CP-01-009)"
            )
        return event.model_copy(update={"proposer_profile": fetched})
    raise VultronValidationError(
        f"{type(event).__name__} has no slot for the handed-off object"
        f" {reference.object_id!r}"
    )


def _case_names(case: VulnerabilityCase, object_id: str) -> bool:
    """True when *case*'s own file names *object_id*."""
    named = [
        *(entry.embargo_id for entry in case.embargo_register),
        *(_id_of(p) for p in case.case_participants),
        *(_id_of(r) for r in case.vulnerability_reports),
        *(_id_of(s) for s in case.case_statuses),
        *case.notes,
    ]
    return object_id in named


def case_object_for_participant(
    dl: CasePersistence,
    host_actor_id: str,
    case_id: str,
    object_id: str,
    requester_id: str,
) -> PersistableModel:
    """The case host's read: *object_id*, as *case_id*'s host holds it.

    Served only by the case's CASE_MANAGER, *host_actor_id*, whose store
    *dl* is: a participant's replica is not the case host.  Served only to
    an active participant of the case (CM-10-004) that has not closed, as
    case content is sent only to one (CM-23-004, :func:`may_act_on_case`),
    and only an object the case names, or one scoped to it by its
    ``context`` (AKM-05-006).
    *requester_id* is the actor the request claims to be: the prototype
    authenticates nobody (#509).

    Raises:
        VultronNotFoundError: When the case or the object is not held, the
            host is not the case's CASE_MANAGER, or the case does not name
            the object.  The answer is the same for an object the host holds
            under another case, so the read tells a participant nothing
            about cases it is not in.
        VultronNotACaseParticipantError: When *requester_id* is not an active
            participant of the case, or has closed on it.
    """
    case = dl.read_case(case_id)
    if case is None:
        raise VultronNotFoundError("VulnerabilityCase", case_id)
    manager_id = resolve_case_manager_id(case, dl)
    if manager_id is None or not same_actor_id(manager_id, host_actor_id):
        raise VultronNotFoundError("VulnerabilityCase", case_id)
    requester = normalise_actor_id(requester_id)
    if not may_act_on_case(case, dl, requester):
        raise VultronNotACaseParticipantError(case.id_, requester)
    if object_id == case.id_:
        return case
    found = dl.read(object_id)
    if found is None:
        raise VultronNotFoundError("Object", object_id)
    if not (
        _case_names(case, object_id)
        or _id_of(getattr(found, "context", None)) == case.id_
    ):
        raise VultronNotFoundError("Object", object_id)
    logger.info(
        "case object read: served '%s' of case '%s' to actor_id=%s",
        object_id,
        case.id_,
        requester,
    )
    return found


__all__ = [
    "case_object_for_participant",
    "references_to_fetch",
    "with_fetched_object",
]
