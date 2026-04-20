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
Trigger router for actor-level participant behaviors.

Thin wrapper: validates request → calls adapter → returns response.
All domain logic lives in vultron.core.use_cases.triggers.actor.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, Path, status

from vultron.adapters.driving.fastapi._trigger_adapter import (
    accept_case_invite_trigger,
    suggest_actor_to_case_trigger,
)
from vultron.adapters.driving.fastapi.outbox_handler import outbox_handler
from vultron.adapters.driving.fastapi.trigger_models import (
    AcceptCaseInviteRequest,
    SuggestActorToCaseRequest,
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
    "/{actor_id}/trigger/suggest-actor-to-case",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Suggest another actor for a case.",
    description=(
        "Emits a RecommendActorActivity addressed to the case owner "
        "(typically the CaseActor).  The CaseActor then autonomously "
        "invites the suggested actor via RmInviteToCaseActivity."
    ),
    operation_id="actors_trigger_suggest_actor_to_case",
)
def trigger_suggest_actor_to_case(
    actor_id: str,
    body: SuggestActorToCaseRequest,
    background_tasks: BackgroundTasks,
    dl: DataLayer = Depends(_actor_dl),
    actor_dl: DataLayer = Depends(_canonical_actor_dl),
) -> dict:
    """
    Trigger the suggest-actor-to-case behavior for the given actor.

    Implements:
        TB-01-001, TB-01-002, TB-01-003, TB-02-001, TB-03-001, TB-03-002,
        TB-04-001
    """
    result = suggest_actor_to_case_trigger(
        actor_id=actor_id,
        case_id=body.case_id,
        suggested_actor_id=body.suggested_actor_id,
        dl=dl,
    )
    background_tasks.add_task(outbox_handler, actor_id, actor_dl, dl)
    return result


@router.post(
    "/{actor_id}/trigger/accept-case-invite",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Accept a case invitation.",
    description=(
        "Accepts an RmInviteToCaseActivity by emitting an "
        "RmAcceptInviteToCaseActivity queued in the actor's outbox for "
        "delivery to the case owner."
    ),
    operation_id="actors_trigger_accept_case_invite",
)
def trigger_accept_case_invite(
    actor_id: str,
    body: AcceptCaseInviteRequest,
    background_tasks: BackgroundTasks,
    dl: DataLayer = Depends(_actor_dl),
    actor_dl: DataLayer = Depends(_canonical_actor_dl),
) -> dict:
    """
    Trigger the accept-case-invite behavior for the given actor.

    Implements:
        TB-01-001, TB-01-002, TB-01-003, TB-02-001, TB-03-001, TB-03-002,
        TB-04-001
    """
    result = accept_case_invite_trigger(
        actor_id=actor_id,
        invite_id=body.invite_id,
        dl=dl,
    )
    background_tasks.add_task(outbox_handler, actor_id, actor_dl, dl)
    return result
