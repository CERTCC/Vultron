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

"""
Trigger router for embargo-management behaviors.

Thin wrapper: validates request → calls adapter → returns response.
All domain logic lives in vultron.core.use_cases.triggers.embargo.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, Path, status

from vultron.adapters.driving.fastapi._trigger_adapter import (
    accept_embargo_trigger,
    propose_embargo_revision_trigger,
    propose_embargo_trigger,
    reject_embargo_trigger,
    terminate_embargo_trigger,
)
from vultron.adapters.driving.fastapi.outbox_handler import outbox_handler
from vultron.adapters.driving.fastapi.trigger_models import (
    AcceptEmbargoRequest,
    ProposeEmbargoRequest,
    ProposeEmbargoRevisionRequest,
    RejectEmbargoRequest,
    TerminateEmbargoRequest,
)
from vultron.core.ports.datalayer import DataLayer
from vultron.adapters.driven.datalayer import get_datalayer

router = APIRouter(prefix="/actors", tags=["Triggers"])


def _actor_dl(actor_id: str = Path(...)) -> DataLayer:  # noqa: ARG001
    """FastAPI dependency: return the shared DataLayer for trigger use cases.

    Operational data (actors, offers, reports, cases) is stored in the shared
    DataLayer.  The ``actor_id`` path parameter is accepted but unused so that
    ``app.dependency_overrides[_actor_dl]`` works in tests (ADR-0012).
    """
    return get_datalayer()


def _canonical_actor_dl(
    actor_id: str = Path(...),
    dl: DataLayer = Depends(_actor_dl),
) -> DataLayer:
    """FastAPI dependency: actor-scoped DataLayer keyed by the canonical URI.

    Resolves *actor_id* (which may be a short UUID from the URL path) to the
    actor's full canonical URI via the shared DataLayer, then returns the
    actor-scoped DataLayer instance keyed by that URI.  This ensures that
    ``outbox_handler`` reads from the same ``{canonical_uri}_outbox`` table
    that ``record_outbox_item`` wrote to during use-case execution
    (BUG-2026040901).
    """
    actor = dl.read(actor_id) or dl.find_actor_by_short_id(actor_id)
    canonical_id = actor.id_ if actor and hasattr(actor, "id_") else actor_id
    return get_datalayer(canonical_id)


@router.post(
    "/{actor_id}/trigger/propose-embargo",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger an embargo proposal.",
    description=(
        "Triggers the propose-embargo behavior for the given actor. "
        "Creates a new EmbargoEvent and emits an EmProposeEmbargoActivity "
        "(Invite(EmbargoEvent)) activity. "
        "EM state transitions: N → P (new proposal) or A → R (revision). "
        "Returns the resulting activity in the response body (TB-04-001)."
    ),
    operation_id="actors_trigger_propose_embargo",
)
def trigger_propose_embargo(
    actor_id: str,
    body: ProposeEmbargoRequest,
    background_tasks: BackgroundTasks,
    dl: DataLayer = Depends(_actor_dl),
    actor_dl: DataLayer = Depends(_canonical_actor_dl),
) -> dict:
    """
    Trigger the propose-embargo behavior for the given actor.

    Implements:
        TB-01-001, TB-01-002, TB-01-003, TB-02-002, TB-03-001, TB-03-002,
        TB-03-003, TB-04-001, TB-06-001, TB-06-002, TB-07-001
    """
    result = propose_embargo_trigger(
        actor_id, body.case_id, body.note, body.end_time, dl
    )
    background_tasks.add_task(outbox_handler, actor_id, actor_dl, dl)
    return result


@router.post(
    "/{actor_id}/trigger/accept-embargo",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger embargo acceptance (accept a proposal).",
    description=(
        "Triggers the accept-embargo behavior for the given actor. "
        "Accepts the current (or specified) embargo proposal by emitting "
        "an EmAcceptEmbargoActivity activity. Activates the embargo on the case "
        "(EM state → ACTIVE). "
        "Returns the resulting activity in the response body (TB-04-001)."
    ),
    operation_id="actors_trigger_accept_embargo",
)
def trigger_accept_embargo(
    actor_id: str,
    body: AcceptEmbargoRequest,
    background_tasks: BackgroundTasks,
    dl: DataLayer = Depends(_actor_dl),
    actor_dl: DataLayer = Depends(_canonical_actor_dl),
) -> dict:
    """
    Trigger the accept-embargo behavior for the given actor.

    Implements:
        TB-01-001, TB-01-002, TB-01-003, TB-02-002, TB-03-001, TB-03-002,
        TB-04-001, TB-06-001, TB-06-002, TB-07-001
    """
    result = accept_embargo_trigger(
        actor_id, body.case_id, body.proposal_id, dl
    )
    background_tasks.add_task(outbox_handler, actor_id, actor_dl, dl)
    return result


@router.post(
    "/{actor_id}/trigger/reject-embargo",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger embargo rejection (reject a proposal).",
    description=(
        "Triggers the reject-embargo behavior for the given actor. "
        "Rejects the current (or specified) embargo proposal by emitting "
        "an EmRejectEmbargoActivity activity. "
        "EM state transitions: PROPOSED → NO_EMBARGO or REVISE → ACTIVE. "
        "Returns the resulting activity in the response body (TB-04-001)."
    ),
    operation_id="actors_trigger_reject_embargo",
)
def trigger_reject_embargo(
    actor_id: str,
    body: RejectEmbargoRequest,
    background_tasks: BackgroundTasks,
    dl: DataLayer = Depends(_actor_dl),
    actor_dl: DataLayer = Depends(_canonical_actor_dl),
) -> dict:
    """
    Trigger the reject-embargo behavior for the given actor.

    Implements:
        TB-01-001, TB-01-002, TB-01-003, TB-02-002, TB-03-001, TB-03-002,
        TB-04-001, TB-06-001, TB-06-002, TB-07-001
    """
    result = reject_embargo_trigger(
        actor_id, body.case_id, body.proposal_id, dl
    )
    background_tasks.add_task(outbox_handler, actor_id, actor_dl, dl)
    return result


@router.post(
    "/{actor_id}/trigger/propose-embargo-revision",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger an embargo revision proposal.",
    description=(
        "Triggers the propose-embargo-revision behavior for the given actor. "
        "Proposes a revision to the active embargo by emitting an "
        "EmProposeEmbargoActivity activity. "
        "Only valid when EM state is ACTIVE or REVISE; "
        "use propose-embargo for initial proposals. "
        "EM state transitions: ACTIVE → REVISE or REVISE → REVISE. "
        "Returns the resulting activity in the response body (TB-04-001)."
    ),
    operation_id="actors_trigger_propose_embargo_revision",
)
def trigger_propose_embargo_revision(
    actor_id: str,
    body: ProposeEmbargoRevisionRequest,
    background_tasks: BackgroundTasks,
    dl: DataLayer = Depends(_actor_dl),
    actor_dl: DataLayer = Depends(_canonical_actor_dl),
) -> dict:
    """
    Trigger the propose-embargo-revision behavior for the given actor.

    Implements:
        TB-01-001, TB-01-002, TB-01-003, TB-02-002, TB-03-001, TB-03-002,
        TB-03-003, TB-04-001, TB-06-001, TB-06-002, TB-07-001
    """
    result = propose_embargo_revision_trigger(
        actor_id, body.case_id, body.note, body.end_time, dl
    )
    background_tasks.add_task(outbox_handler, actor_id, actor_dl, dl)
    return result


@router.post(
    "/{actor_id}/trigger/terminate-embargo",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger embargo termination.",
    description=(
        "Triggers the terminate-embargo behavior for the given actor. "
        "Announces the end of the active embargo by emitting an "
        "AnnounceEmbargoActivity activity. Updates the case EM state to EXITED "
        "and clears the active embargo. "
        "Returns HTTP 409 if no active embargo exists. "
        "Returns the resulting activity in the response body (TB-04-001)."
    ),
    operation_id="actors_trigger_terminate_embargo",
)
def trigger_terminate_embargo(
    actor_id: str,
    body: TerminateEmbargoRequest,
    background_tasks: BackgroundTasks,
    dl: DataLayer = Depends(_actor_dl),
    actor_dl: DataLayer = Depends(_canonical_actor_dl),
) -> dict:
    """
    Trigger the terminate-embargo behavior for the given actor.

    Implements:
        TB-01-001, TB-01-002, TB-01-003, TB-02-002, TB-03-001, TB-03-002,
        TB-04-001, TB-06-001, TB-06-002, TB-07-001
    """
    result = terminate_embargo_trigger(actor_id, body.case_id, dl)
    background_tasks.add_task(outbox_handler, actor_id, actor_dl, dl)
    return result
