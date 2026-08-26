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
from typing import TYPE_CHECKING, Any, TypeVar

from vultron.core.ports.case_persistence import (
    CaseOutboxPersistence,
    CasePersistence,
)
from vultron.errors import VultronNotFoundError
from vultron.wire.as2.vocab.base.base import as_Base

if TYPE_CHECKING:  # pragma: no cover - deferred to avoid a wire import cycle
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        as_VulnerabilityCase,
    )

#: Serialisation options for every outbound activity dict this adapter returns.
#:
#: ``serialize_as_any=True`` is load bearing, not cosmetic. Without it Pydantic
#: serialises each field by its *declared* type, so an inline nested object held
#: in a field typed as a reference union is flattened — for
#: ``as_CaseProposal.object_`` (declared ``ActivityStreamRequiredRef[
#: as_VulnerabilityReport]``) the report came out as ``null``, putting a proposal
#: on the wire with no report at all in breach of CP-01-004. The receiver then had
#: nothing to store, and everything derived from the report — the reporter
#: participant, its ledger entry, the SIGNATORY seed — skipped "best-effort", so
#: the reporter silently never received a case replica.
#:
#: The same flag is required on the delivery path and in the test router, both of
#: which say so; this is the third place that needs it.
_DUMP_KWARGS: dict[str, Any] = {
    "by_alias": True,
    "exclude_none": True,
    "serialize_as_any": True,
}

logger = logging.getLogger(__name__)

_BM = TypeVar("_BM", bound=as_Base)


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


def _case_for_wire(
    dl: CasePersistence, case_id: str
) -> "as_VulnerabilityCase":
    """Return the stored case as a wire object, with its embargo carried inline.

    Takes the narrow read port rather than the full ``DataLayer``: reading is all
    this does, and every caller holds a ``CaseOutboxPersistence``
    (``_TriggerAdapterBase._dl``), which is a ``CasePersistence``.

    Every activity that puts a case on the wire goes through here, because
    ``active_embargo`` is a reference the *receiver* cannot dereference: it may
    not hold the ``EmbargoEvent``, and no dereferencing mechanism is specified
    (AKM-03-001, the same rule as CP-01-004). Sending the id alone therefore
    hands the recipient a case pointing at an object it can never read.

    That is not hypothetical. A CaseActor holding such a case tore the embargo
    down locally and then could not announce it: ``terminate_embargo`` begins by
    reading the ``EmbargoEvent`` it is about, so it raised
    ``VultronNotFoundError`` mid-sequence and no ``Remove(EmbargoEvent, Case)``
    was ever emitted. Every other participant's replica kept an embargo the
    manager had already removed, EM stayed ACTIVE for all of them, and nothing
    surfaced — the receiving side had no way to tell a missing object from an
    embargo that was genuinely still active.

    ``as_VulnerabilityCase.active_embargo`` is an ``as_EmbargoEventRef``, so it
    admits the object; ``to_core()`` reduces it back to an id, so a receiver's
    stored case is unchanged in shape. The recipient stores the carried object
    separately (see ``_store_embedded_embargo``), which is what makes the id
    resolve on its side too.
    """
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        as_VulnerabilityCase,
    )

    case = _to_wire(dl.read(case_id), as_VulnerabilityCase)
    embargo_ref = getattr(case, "active_embargo", None)
    if not isinstance(embargo_ref, str) or not embargo_ref:
        # Already an object, or no embargo at all — nothing to carry.
        return case

    from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

    stored = dl.read(embargo_ref)
    if stored is None:
        # The sender does not hold it either. Left as an id: this function's job
        # is to carry what is there, and a sender-side gap is the business of
        # whoever wrote the dangling reference.
        logger.warning(
            "_case_for_wire: case '%s' references active_embargo '%s' which is"
            " absent from the sending actor's own store, so it cannot be"
            " carried inline (AKM-03-001); the recipient will receive an"
            " unresolvable reference",
            case_id,
            embargo_ref,
        )
        return case
    try:
        case.active_embargo = _to_wire(stored, as_EmbargoEvent)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "_case_for_wire: could not project active_embargo '%s' of case"
            " '%s' to its wire shape (%s); sending the reference alone",
            embargo_ref,
            case_id,
            exc,
        )
    return case


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
