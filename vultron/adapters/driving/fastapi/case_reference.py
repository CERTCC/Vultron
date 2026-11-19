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

"""Resolve a client's case reference to the case it names, at the edge.

A client names a case by its full id or by its short id (the surrogate key,
the last segment of its id: ``find_case_by_short_id``).  The core works with
the full id only, so the driving adapter turns the reference into the full id
before it hands a request on (ADR-0032: validate at the edge, promote to the
core).  A trigger request's ``case_id`` seeds the tree's ``/case_id`` key
(BT-25-007), and that seed is a copy, never a store read (BT-25-009,
ADR-0207), so the edge is the only place the short id can become the full id.
"""

from typing import Any, TypeVar, cast

from vultron.core.models.case import VulnerabilityCase
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.datalayer import DataLayer
from vultron.core.use_cases.triggers import _helpers as trigger_helpers
from vultron.core.use_cases.triggers.request_bodies import CaseTriggerRequest
from vultron.core.use_cases.triggers.requests import TriggerRequest
from vultron.errors import VultronNotFoundError

RequestT = TypeVar("RequestT", bound=TriggerRequest[Any])


def find_case(case_ref: str, dl: DataLayer) -> VulnerabilityCase | None:
    """The case *case_ref* names in *dl*, by full id or short id, or ``None``.

    The lookup is the triggers' own (``find_case``), so the edge and the
    core cannot disagree about which case a reference names.
    """
    # The route's store is typed as the narrow ``DataLayer`` port; the case
    # read needs ``CasePersistence``, which every concrete store satisfies.
    return trigger_helpers.find_case(case_ref, cast(CasePersistence, dl))


def require_case_id(case_ref: str, dl: DataLayer, actor_id: str) -> str:
    """The full id of the case *case_ref* names in *dl*.

    A miss is refused with the error the trigger use case raises for it: an
    unknown requesting actor first, as the trigger resolves its actor before
    its case (an unknown actor's store holds no case at all), then the case.

    Raises:
        VultronNotFoundError: *actor_id* names no actor *dl* holds, or *dl*
            holds no case *case_ref* names.  Each names the reference as the
            client sent it.
    """
    case = find_case(case_ref, dl)
    if case is None:
        trigger_helpers.resolve_actor(actor_id, cast(CasePersistence, dl))
        raise VultronNotFoundError("VulnerabilityCase", case_ref)
    return case.id_


def with_full_case_id(request: RequestT, dl: DataLayer) -> RequestT:
    """*request* naming its case by full id, or unchanged if it names none.

    A :class:`CaseTriggerRequest` whose ``case_id`` is a short id is copied
    with the case's full id, so the core never receives a short id.

    Raises:
        VultronNotFoundError: *request* is case-scoped and names a case, or
            an actor, *dl* does not hold (:func:`require_case_id`).
    """
    if not isinstance(request, CaseTriggerRequest):
        return request
    case_id = require_case_id(request.case_id, dl, request.actor_id)
    if case_id == request.case_id:
        return request
    return request.model_copy(update={"case_id": case_id})


__all__ = ["find_case", "require_case_id", "with_full_case_id"]
