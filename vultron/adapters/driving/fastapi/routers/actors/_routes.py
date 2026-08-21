#!/usr/bin/env python
"""
Route handlers for the Vultron FastAPI actors router.

Defines the ``/actors`` APIRouter and all its endpoints.  Route-level
dependencies and business logic delegated to ``_lookup`` and ``_inbox``
helpers; no direct DataLayer manipulation here beyond what FastAPI
dependencies provide.
"""

#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

import logging
from typing import Any, Literal, cast
from uuid import uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    status,
)
from pydantic import BaseModel, Field

from vultron.adapters.driven import actor_hosts
from vultron.adapters.driven.db_record import object_to_record
from vultron.adapters.driven.datalayer import get_datalayer
from vultron.adapters.driving.fastapi.deps import get_actor_dl, node_base_url
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    run_inbox_pipeline,
)
from vultron.adapters.driving.fastapi.outbox_handler import outbox_handler
from vultron.adapters.driving.fastapi.responses import AS2JSONResponse
from vultron.adapters.utils import strip_id_prefix
from vultron.core.models.actor import (
    CoreActor,
    VultronOrganization,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.protocols import PersistableModel
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.datalayer import DataLayer
from vultron.core.use_cases.query.action_rules import (
    ActionRulesRequest,
    GetActionRulesUseCase,
)
from vultron.errors import VultronNotFoundError, VultronValidationError
from vultron.wire.as2.vocab.base.links import as_Link
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.base import as_Object
from vultron.wire.as2.vocab.base.objects.collections import (
    as_OrderedCollection,
)

from vultron.adapters.driving.fastapi.routers.actors._inbox import (
    _activity_addressed_to,
    _activity_already_received,
    _get_body,
    _record_inbox_receipt,
    parse_activity,
)
from vultron.adapters.driving.fastapi.routers.actors._lookup import (
    _ACTOR_RECORD_TYPES,
    _ACTOR_TYPE_MAP,
    _actor_class_for_record,
    _find_actor_record,
    _resolve_actor_or_404,
)

AnyActor = CoreActor

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/actors", tags=["Actors"])


@router.get(
    "/",
    description="Returns a list of Actor examples.",
    operation_id="actors_list",
)
def get_actors():
    """Returns the actors this node hosts.

    Under ADR-0070 this enumerates hosted actors and reads each one's record
    from its own store.  It previously scanned a shared pool for every
    actor-typed row, which also returned the node's *peers* — actors it merely
    holds an address for.  A peer is not hosted here, so peers are no longer
    listed (ADR-0070 decision 4).
    """
    objects: list[AnyActor] = []
    for actor_id in actor_hosts.hosted_actor_ids():
        actor_dl = get_datalayer(actor_id)
        for t in _ACTOR_RECORD_TYPES:
            rec = actor_dl.get(t, actor_id)
            if isinstance(rec, dict):
                cls = _actor_class_for_record(rec)
                objects.append(cls.model_validate(rec.get("data_", {})))
                break

    logger.debug("get_actors: found %d hosted actor(s)", len(objects))

    return AS2JSONResponse(
        [
            o.model_dump(mode="json", by_alias=True, exclude_none=True)
            for o in objects
        ]
    )


class ActorCreateRequest(BaseModel):
    """Request body for ``POST /actors/`` (D5-1-G2).

    Creates a new actor record in that actor's own store.  The operation is
    idempotent: if ``id`` is supplied and an actor with that URI already
    exists, the existing record is returned with HTTP 200.
    """

    name: str = Field(description="Display name of the actor.")
    actor_type: Literal[
        "Person", "Organization", "Service", "Application", "Group"
    ] = Field(
        default="Organization",
        description="ActivityStreams actor type.",
    )
    id_: str | None = Field(
        default=None,
        alias="id",
        description=(
            "Full URI for the actor.  Omit to let the server derive one "
            "from ``VULTRON_SERVER__BASE_URL``."
        ),
    )

    model_config = {"populate_by_name": True}


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Create Actor",
    description=(
        "Creates a new actor record in that actor's own store. "
        "Idempotent: if an actor with the same ``id`` already exists the "
        "existing record is returned with HTTP 200."
    ),
    operation_id="actors_create",
)
def create_actor(request: ActorCreateRequest, http_request: Request):
    """Create (or return existing) actor record in that actor's own store.

    An actor is a process with API endpoints, and its id **is** the URL that
    reaches it: an actor this node hosts is named
    ``{base_url}/actors/{slug}``, and its inbox is ``{id}/inbox``. So the id is
    canonicalized *before* the record is built, not only when choosing the store.

    An unspecified id becomes a fresh **slug**, not a generated URI. Passing
    ``make_id("actors")`` here did not work: it builds on ``adapters.utils
    .BASE_URL`` rather than ``ServerConfig.base_url``, yielding
    ``…/api/actors/{uuid}`` — no ``v2`` segment — and because that value already
    carries a scheme, ``canonical_actor_uri`` returns it verbatim instead of
    adopting it. The record's id then named an endpoint this node does not serve,
    so its store was reachable under one id and ``GET /actors/{slug}`` resolved to
    another. Handing the canonicalizer a bare slug is what makes the id and the
    serving endpoint the same string by construction (ADR-0070 decision 2).

    A client-supplied id under another authority is not rejected here, but note
    that it names a process *elsewhere* — a peer, whose address a hosted actor may
    know (ADR-0070 decision 5). It is canonicalized to this node's namespace
    rather than adopted verbatim, because this node cannot serve an endpoint it
    does not own.

    "This node's namespace" is the *serving app's* base URL where it declares one
    (``deps.node_base_url``), falling back to configuration. Creating an actor and
    then addressing it have to agree on that namespace, or the record lands in a
    store no request can reach.
    """
    actor_id = actor_hosts.canonical_actor_uri(
        request.id_ or str(uuid4()),
        base_url=node_base_url(http_request),
    )
    datalayer = get_datalayer(actor_id)

    # Idempotency: return existing record unchanged.
    existing = _find_actor_record(datalayer, actor_id)
    if existing is not None:
        cls = _actor_class_for_record(existing)
        data = existing.get("data_", {})
        return AS2JSONResponse(
            cls.model_validate(data).model_dump(
                mode="json", by_alias=True, exclude_none=True
            ),
            status_code=status.HTTP_200_OK,
        )

    actor_cls = _ACTOR_TYPE_MAP.get(request.actor_type, VultronOrganization)
    actor = actor_cls(id_=actor_id, name=request.name)
    datalayer.create(object_to_record(cast(PersistableModel, actor)))
    logger.info("Created actor %s (type=%s)", actor_id, request.actor_type)
    return AS2JSONResponse(
        actor.model_dump(mode="json", by_alias=True, exclude_none=True),
        status_code=status.HTTP_201_CREATED,
    )


@router.get(
    "/{actor_id:path}/profile",
    summary="Get Actor Profile",
    description=(
        "Returns an ActivityStreams actor profile including inbox and outbox "
        "URLs for actor discovery and federation."
    ),
    operation_id="actors_get_profile",
)
def get_actor_profile(
    actor_id: str, datalayer: DataLayer = Depends(get_actor_dl)
):
    """Returns an actor's discovery profile.

    Includes actor metadata (name, type), inbox URL, outbox URL, and any
    other ActivityStreams profile fields present on the actor.  Intended
    for use by remote systems discovering how to interact with this actor.
    The `inbox` and `outbox` fields are returned as URL strings, not
    embedded collection objects.
    """
    actor_record = _find_actor_record(datalayer, actor_id)
    if not actor_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Actor not found."
        )

    actor_cls = _actor_class_for_record(actor_record)
    as_actor = cast(
        Any, actor_cls.model_validate(actor_record.get("data_", {}))
    )
    profile = as_actor.model_dump(
        mode="json", by_alias=True, exclude_none=True
    )
    inbox = getattr(as_actor, "inbox", None)
    outbox = getattr(as_actor, "outbox", None)
    profile["inbox"] = (
        inbox
        if isinstance(inbox, str)
        else (
            inbox.get("id")
            if isinstance(inbox, dict)
            else getattr(inbox, "id_", None)
        )
    )
    profile["outbox"] = (
        outbox
        if isinstance(outbox, str)
        else (
            outbox.get("id")
            if isinstance(outbox, dict)
            else getattr(outbox, "id_", None)
        )
    )
    return AS2JSONResponse(profile)


@router.get(
    "/{actor_id:path}/cases/{case_id}/action-rules",
    summary="Get CVD Action Rules for an Actor in a Case",
    description=(
        "Returns the set of valid CVD actions available to an actor in a "
        "specific case. The actor/case pair is resolved to the matching "
        "CaseParticipant internally."
    ),
    operation_id="actors_get_action_rules",
)
def get_action_rules(
    actor_id: str,
    case_id: str,
    dl: DataLayer = Depends(get_actor_dl),
) -> dict:
    """Return valid CVD actions for an actor in a specific case."""
    try:
        canonical = actor_hosts.canonical_actor_uri(actor_id)
        actor_obj = dl.read(canonical) or dl.read(actor_id)
        case_obj = dl.read(case_id)
        if case_obj is None or not isinstance(case_obj, VulnerabilityCase):
            case_obj = dl.find_case_by_short_id(case_id)
        if case_obj is None or not isinstance(case_obj, VulnerabilityCase):
            raise VultronNotFoundError("VulnerabilityCase", case_id)
        canonical_actor_id = canonical
        if actor_obj is not None and hasattr(actor_obj, "id_"):
            canonical_actor_id = actor_obj.id_
        else:
            actor_index = getattr(case_obj, "actor_participant_index", {})
            if isinstance(actor_index, dict):
                for candidate_id in actor_index:
                    if (
                        candidate_id == actor_id
                        or candidate_id.endswith(f"/{actor_id}")
                        or strip_id_prefix(candidate_id) == actor_id
                    ):
                        canonical_actor_id = candidate_id
                        break
        req = ActionRulesRequest(
            case_id=case_obj.id_, actor_id=canonical_actor_id
        )
        # `dl` is typed as the narrow `DataLayer` port but this use case needs
        # case-aware reads.  `SqliteDataLayer` satisfies both protocols
        # structurally; a bare `DataLayer` does not, because
        # `CasePersistence.clone_for_actor` returns a `CasePersistence`.
        return GetActionRulesUseCase(
            dl=cast(CasePersistence, dl), request=req
        ).execute()
    except VultronNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except VultronValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )


@router.get(
    "/{actor_id:path}/inbox",
    response_model=as_OrderedCollection,
    summary="Get Actor Inbox",
    description="Returns the Actor's Inbox. (stub implementation).",
    operation_id="actors_get_inbox",
)
def get_actor_inbox(
    actor_id: str, datalayer: DataLayer = Depends(get_actor_dl)
) -> AS2JSONResponse:
    """Returns the Actor's Inbox."""
    from vultron.core.models.base import CoreObject as _CoreObject

    # 404 if this node does not host the addressed actor.  No clone is needed:
    # the injected DataLayer already *is* this actor's store (ADR-0070).
    _resolve_actor_or_404(actor_id, datalayer)
    items = cast(
        list[as_Object | as_Link | str | _CoreObject | None],
        list(cast(Any, datalayer).inbox_list()),
    )
    return AS2JSONResponse(as_OrderedCollection(items=items))


@router.post(
    "/{actor_id:path}/inbox/",
    summary="Add an Activity to the Actor's Inbox.",
    description="Adds an Activity to the Actor's Inbox. (stub implementation).",
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="actors_post_inbox",
)
def post_actor_inbox(
    actor_id: str,
    # as_Activity is a problem, because its subclasses have different required fields,
    # so we really want to accept any subclass that we have a registered handler for here.
    request: Request,
    background_tasks: BackgroundTasks,
    activity: as_Activity = Depends(parse_activity),
    body: dict[str, Any] = Depends(_get_body),
    dl: DataLayer = Depends(get_actor_dl),
) -> None:
    """Adds an item to the Actor's Inbox.
    The 202 Accepted status code indicates that the request has been accepted for
    processing, but the processing has not been completed. This is appropriate here
    because the inbox processing is handled asynchronously in the background.

    Policy logic lives in ``process_payload`` (core BT module); this
    endpoint is thin glue that supplies adapter implementations and
    schedules the background task (IO-03-003).

    Args:
        actor_id: The ID of the Actor whose Inbox to add the item to.
        request: The FastAPI Request (used to resolve the per-app emitter/dispatcher).
        activity: The Activity item (parsed by the ``parse_activity`` dependency).
        body: Raw JSON request body dict (needed for nested object re-parsing).
        background_tasks: FastAPI BackgroundTasks instance to schedule background tasks.
    Returns:
        None
    Raises:
        HTTPException: If the Actor is not found.
    """
    actor = _resolve_actor_or_404(actor_id, dl)
    canonical_actor_id = actor.id_

    if not _activity_addressed_to(activity, canonical_actor_id, dl=dl):
        logger.warning(
            "Activity %s is not addressed to actor %s; refusing (IE-11-001).",
            activity.id_,
            canonical_actor_id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Activity is not addressed to actor {canonical_actor_id}.",
        )

    if _activity_already_received(actor, activity.id_):
        logger.debug(
            "Activity %s already received by %s; ignoring duplicate submission.",
            activity.id_,
            canonical_actor_id,
        )
        return None

    # Record receipt synchronously so the dedup guard on the next delivery
    # of the same activity_id sees the updated actor inbox record.
    _record_inbox_receipt(dl, actor, activity.id_, canonical_actor_id)

    emitter = getattr(request.app.state, "emitter", None)
    dispatcher = getattr(request.app.state, "dispatcher", None)

    background_tasks.add_task(
        run_inbox_pipeline,
        activity,
        body,
        dl,
        canonical_actor_id,
        dispatcher,
        emitter,
    )
    return None


@router.post(
    "/{actor_id:path}/outbox/",
    summary="Add an Activity to the Actor's Outbox.",
    description="Adds an Activity to the Actor's Outbox. (stub implementation).",
    status_code=status.HTTP_200_OK,
    operation_id="actors_post_outbox",
)
def post_actor_outbox(
    actor_id: str,
    activity: as_Activity,
    request: Request,
    background_tasks: BackgroundTasks,
    dl: DataLayer = Depends(get_actor_dl),
) -> None:
    """Adds an item to the Actor's Outbox.
    Args:
        actor_id: The ID of the Actor whose Outbox to add the item to.
        activity: The Activity item to add to the Outbox.
        request: The FastAPI Request (used to resolve the per-app emitter).
        background_tasks: FastAPI BackgroundTasks instance to schedule background tasks.
    Returns:
        None
    Raises:
        HTTPException: If the Actor is not found.
    """
    actor = _resolve_actor_or_404(actor_id, dl)
    canonical_actor_id = actor.id_

    # actor.id_ must match activity.actor or activity.actor.id_
    if isinstance(activity.actor, str):
        activity_actor_id = activity.actor
    elif activity.actor is not None and hasattr(activity.actor, "id_"):
        activity_actor_id = activity.actor.id_
    else:
        activity_actor_id = None

    if activity_actor_id != canonical_actor_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Activity actor does not match actor_id.",
        )

    logger.debug(
        f"Posting activity to actor {canonical_actor_id} outbox: {activity}"
    )

    # No clone: the injected DataLayer already is this actor's store.
    actor_dl = cast(Any, dl)
    actor_dl.create(object_to_record(activity))
    actor_dl.outbox_append(activity.id_)

    emitter = getattr(request.app.state, "emitter", None)
    # Keyword, not positional: `outbox_handler`'s third parameter used to be a
    # second DataLayer (the shared one), so a positional third argument reads as
    # a store here and silently becomes the emitter.  See the ratchet in
    # test/architecture/test_outbox_handler_emitter_keyword.py.
    background_tasks.add_task(
        outbox_handler, canonical_actor_id, actor_dl, emitter=emitter
    )

    return None


@router.get(
    "/{actor_id:path}",
    description="Returns an Actor by surrogate key or canonical ID.",
    operation_id="actors_get",
)
def get_actor(actor_id: str, datalayer: DataLayer = Depends(get_actor_dl)):
    """Returns an Actor by actor_id.

    Accepts either a canonical actor ID or the actor's surrogate key.
    """
    actor = _find_actor_record(datalayer, actor_id)
    if not actor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Actor not found."
        )

    cls = _actor_class_for_record(actor)
    data = actor.get("data_", {})
    return AS2JSONResponse(
        cls.model_validate(data).model_dump(
            mode="json", by_alias=True, exclude_none=True
        )
    )
