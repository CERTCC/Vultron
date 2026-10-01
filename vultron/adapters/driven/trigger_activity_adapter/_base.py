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

"""Shared constants and base class for TriggerActivityAdapter submodules."""

import logging
from typing import Any, TypeVar

from pydantic import BaseModel

from vultron.adapters.driven.db_record import _AS_LIST_REF_FIELDS
from vultron.adapters.outbox_sealed_body import (
    outbound_activity_id,
    seal_outbound_body,
)
from vultron.core.models.base import CoreObject
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.embargo_ordering import read_embargo_event
from vultron.errors import (
    VultronActivityConstructionError,
    VultronNotFoundError,
    VultronValidationError,
)
from vultron.wire.as2.vocab.base.objects.base import as_Object
from vultron.wire.as2.vocab.base.registry import declared_wire_type
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)

_BM = TypeVar("_BM", bound=BaseModel)


def _to_wire(core_obj: Any, wire_cls: type[_BM]) -> _BM:
    """Convert a core domain object to its wire vocabulary counterpart.

    Uses ``wire_cls.from_core(core_obj)`` so that wire classes that override
    ``from_core`` (e.g. ``as_VulnerabilityCase`` which wraps ``case_activity``
    string IDs as stub ``as_Activity`` objects) apply their custom logic.

    Raises:
        VultronNotFoundError: when *core_obj* is ``None`` (dl.read returned
            no match for the requested ID).
    """
    if core_obj is None:
        raise VultronNotFoundError(
            wire_cls.__name__,
            "object not found in DataLayer",
        )
    if isinstance(core_obj, wire_cls):
        return core_obj
    return wire_cls.from_core(core_obj)  # type: ignore[attr-defined,return-value,no-any-return]


def _to_wire_object(core_obj: Any, object_id: str) -> Any:
    """Check that a stored object of any type can be carried, and return it.

    For callers that do not know the object's type in advance
    (``add_object_to_case`` accepts any stored object). Under ADR-0099 detail 3
    a ``CoreObject`` *is* its own wire form, so an ``as_Object`` or a
    ``CoreObject`` is returned unchanged; nothing is converted.

    No vocabulary lookup is made: resolving the object's class name would be a
    name-coincidence lookup ARCH-23-002 forbids, and its answer is always the
    object's own class (ISSUE-3565).

    Raises:
        VultronNotFoundError: when *core_obj* is ``None`` (dl.read returned
            no match for *object_id*) — not a vocabulary error about
            ``'NoneType'``.
        VultronActivityConstructionError: when the object is not an AS2 object
            (a ``CoreRecord`` bookkeeping type, or anything else), or its class
            declares no wire ``type`` (an abstract core class).
    """
    if core_obj is None:
        raise VultronNotFoundError("AS2Object", object_id)
    if isinstance(core_obj, as_Object):
        return core_obj
    type_name = type(core_obj).__name__
    if not isinstance(core_obj, CoreObject):
        raise VultronActivityConstructionError(
            f"object '{object_id}': {type_name!r} is not an AS2 object and"
            " cannot be carried in an activity"
        )
    # Under ADR-0099 an activity's object refs admit any CoreObject, so as_Add
    # does not refuse an abstract one (``CoreActor``) for us. An abstract class
    # declares no ``type`` (its instances fill ``type_`` from the class name),
    # so it has no wire form a receiver could dispatch.
    if declared_wire_type(type(core_obj)) is None:
        raise VultronActivityConstructionError(
            f"object '{object_id}': {type_name!r} declares no wire type"
            " and cannot be carried in an activity"
        )
    return core_obj


def _case_for_wire(
    dl: CasePersistence, case_id: str
) -> "as_VulnerabilityCase":
    """Return the stored case as a wire object with its references carried inline.

    Takes the narrow read port rather than the full ``DataLayer``: reading is all
    this does, and every caller holds a ``CaseOutboxPersistence``
    (``_TriggerAdapterBase._dl``), which is a ``CasePersistence``.

    Every activity that puts a case on the wire goes through here, because a
    reference in the case is one the *receiver* cannot dereference: it may not
    hold the object, and no dereferencing mechanism is specified (AKM-03-001,
    the same rule as CP-01-004). Sending an id alone therefore hands the
    recipient a case pointing at an object it can never read. Three fields
    carry references the recipient needs:

    - ``active_embargo``: a CaseActor holding a case with only the id tore the
      embargo down locally and then could not announce it — ``terminate_embargo``
      begins by reading the ``EmbargoEvent``, so it raised
      ``VultronNotFoundError`` mid-sequence and no ``Remove(EmbargoEvent, Case)``
      was ever emitted; every other replica kept an embargo the manager had
      already removed.
    - ``case_participants``: the recipient of a bootstrap ``Create`` or
      ``Announce`` stores each embedded participant as its own record
      (CBT-05-005, CBT-01-007). With ids alone it has no participant at
      ``RM.RECEIVED`` to move to ``VALID`` and no CASE_MANAGER participant to
      route its reply to. The outbox used to expand these at delivery time
      (``dl.hydrate()``); the sealed body is delivered as built (VM-08-003), so
      the expansion belongs here, where the body is made.
    - ``vulnerability_reports``: the same, for the reports the case names.

    The stored case is untouched — the carried objects live on a ``model_copy``.
    ``as_VulnerabilityCase`` admits the objects in every one of these slots, and
    ``to_core()`` reduces them back to ids, so a receiver's stored case is
    unchanged in shape; the recipient stores each carried object separately
    (``store_carried_embargo``, ``store_embedded_participants``).

    A participant or report reference the sender's own store cannot resolve
    is left as the id with a WARNING: this function's job is to carry what is
    there, and a sender-side gap is the business of whoever wrote the
    dangling reference. ``announce_vulnerability_case`` then refuses to send
    a case whose report is missing (CBT-01-007). An unreadable active embargo
    is the exception: it raises (EMB-18-003, :func:`_carried_embargo`).
    """
    case = _to_wire(dl.read(case_id), as_VulnerabilityCase)
    updates: dict[str, Any] = {}
    embargo = _carried_embargo(dl, case, case_id)
    if embargo is not None:
        updates["active_embargo"] = embargo
    for field_name in _CARRIED_LIST_FIELDS:
        carried = _carried_list(dl, case, case_id, field_name)
        if carried is not None:
            updates[field_name] = carried
    return case.model_copy(update=updates) if updates else case


#: Case list fields whose bare ids are carried as objects by ``_case_for_wire``.
#: ``_AS_LIST_REF_FIELDS`` is the DataLayer's own list of list-reference fields
#: (the ones its retired delivery-time ``hydrate()`` expanded); the reports are
#: added because a recipient seeding a case needs them too (CBT-01-007).
_CARRIED_LIST_FIELDS: frozenset[str] = _AS_LIST_REF_FIELDS | {
    "vulnerability_reports"
}


def _carried_embargo(dl: CasePersistence, case: Any, case_id: str) -> Any:
    """The case's ``active_embargo`` as a wire object, or ``None`` to leave it.

    Fails closed (EMB-18-003): a sender whose case names an active embargo
    its own store cannot read has already broken the invariant, and sending
    the bare id would hand every recipient a case it must refuse.

    Raises:
        VultronValidationError: If the sender does not hold the record, the
            record is not an ``EmbargoEvent``, or it cannot be projected to
            its wire shape -- one error carrying the context, logged once at
            the caller's boundary.
    """
    embargo_ref = getattr(case, "active_embargo", None)
    if not isinstance(embargo_ref, str) or not embargo_ref:
        return None  # already an object, or no embargo at all
    try:
        stored = read_embargo_event(dl, embargo_ref)
    except (VultronNotFoundError, VultronValidationError) as exc:
        raise VultronValidationError(
            f"_case_for_wire: case '{case_id}' names active embargo"
            f" '{embargo_ref}', which the sending actor's own store cannot"
            f" read (EMB-18-003); refusing to send an unresolvable"
            f" reference: {exc}"
        ) from exc
    try:
        return _to_wire(stored, as_EmbargoEvent)
    except Exception as exc:
        raise VultronValidationError(
            f"_case_for_wire: could not project active_embargo"
            f" '{embargo_ref}' of case '{case_id}' to its wire shape: {exc}"
        ) from exc


def _carried_list(
    dl: CasePersistence, case: Any, case_id: str, field_name: str
) -> list[Any] | None:
    """*field_name*'s items with every resolvable bare id replaced by its object.

    Returns ``None`` when nothing changed, so the caller copies nothing.
    """
    items = getattr(case, field_name, None)
    if not isinstance(items, list):
        return None
    carried: list[Any] = []
    changed = False
    for item in items:
        stored = dl.read(item) if isinstance(item, str) and item else None
        if stored is None:
            if isinstance(item, str):
                logger.warning(
                    "_case_for_wire: case '%s' names %s '%s' which is absent"
                    " from the sending actor's own store, so it cannot be"
                    " carried inline (AKM-03-001, CBT-01-007)",
                    case_id,
                    field_name,
                    item,
                )
            carried.append(item)
            continue
        carried.append(stored)
        changed = True
    return carried if changed else None


def _seal(dl: CaseOutboxPersistence, activity: BaseModel) -> tuple[str, str]:
    """Seal *activity*'s outbound body in *dl* and return ``(id, body)``.

    Every adapter method that persists an outbound activity ends here, so the
    text handed back to core is the text the outbox delivers (VM-08-003).
    """
    body = seal_outbound_body(dl, activity)  # refuses an activity with no id_
    return outbound_activity_id(activity), body


class _TriggerAdapterBase:
    """Base class providing DataLayer access to trigger adapter mixins.

    Args:
        dl: The DataLayer for reading persisted objects and creating
            activities.
    """

    def __init__(self, dl: CaseOutboxPersistence) -> None:
        self._dl = dl

    def for_store(self, dl: CaseOutboxPersistence) -> "_TriggerAdapterBase":
        """Return an equivalent adapter that reads and writes *dl* (DL-07-009).

        Opting into
        :func:`~vultron.core.behaviors.store_scope.port_for_store`.  This adapter
        is constructed once per request against the *addressed* actor's store, but
        a delegated emit runs the BT as a different actor — a case owner's
        invite-actor trigger emits from the CaseActor's identity (PCR-08-007).
        Without rebinding, the activity is created here in the requesting actor's
        store while the node queues its id in the executing actor's outbox, so
        delivery finds no such activity and the invitation is never sent
        (ISSUE-2548).

        Returns ``self`` when already bound to *dl*, so the common
        non-delegated case allocates nothing.
        """
        if dl is self._dl:
            return self
        return type(self)(dl)
