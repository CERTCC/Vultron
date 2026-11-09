"""Actor mailbox routes: the inbox delivery target and the outbox post.

The inbox accepts POST only; every other method is answered 405
(IE-02-003, IE-02-004).
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
from typing import Annotated, Any, cast

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)

from vultron.adapters.driven.db_record import object_to_record
from vultron.adapters.driven.sender_sequence_stamp import with_outbound_stamps
from vultron.adapters.driving.fastapi.deps import (
    get_actor_dl,
)
from vultron.adapters.driving.fastapi.errors import unsignable_http_exception
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    run_inbox_pipeline,
)
from vultron.adapters.driving.fastapi.outbox_handler import outbox_handler
from vultron.adapters.driving.fastapi.routers.actors._inbox import (
    VerifiedDelivery,
    _activity_addressed_to,
    parse_activity,
    verified_delivery,
)
from vultron.adapters.driving.fastapi.routers.actors._lookup import (
    _resolve_actor_or_404,
)
from vultron.adapters.outbox_sealed_body import seal_outbound_body
from vultron.core.ports.datalayer import DataLayer
from vultron.wire.as2.errors import VultronUnsignableJsonError

logger = logging.getLogger("uvicorn.error")


router = APIRouter(prefix="/actors", tags=["Actors"])

_INBOX_REFUSED_METHODS = ["GET", "HEAD", "OPTIONS", "PUT", "PATCH", "DELETE"]


@router.api_route(
    "/{actor_id:path}/inbox",
    methods=_INBOX_REFUSED_METHODS,
    include_in_schema=False,
)
@router.api_route(
    "/{actor_id:path}/inbox/",
    methods=_INBOX_REFUSED_METHODS,
    include_in_schema=False,
)
def refuse_non_post_inbox(actor_id: str) -> None:
    """Answer 405 to every non-POST method on the inbox path (IE-02-003).

    The inbox is a delivery target with no read surface (IE-02-004): what an
    actor has received is read from its store through the datalayer router.
    This route exists because ``actors_get`` below is a path catch-all
    (``/{actor_id:path}``); without it an unrouted GET on ``/inbox`` or
    ``/inbox/`` would land there and answer 404 instead of 405.
    """
    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        detail="The inbox accepts POST only.",
        headers={"Allow": "POST"},
    )


@router.post(
    "/{actor_id:path}/inbox",
    status_code=status.HTTP_202_ACCEPTED,
    response_class=Response,
    include_in_schema=False,
)
@router.post(
    "/{actor_id:path}/inbox/",
    summary="Add an Activity to the Actor's Inbox.",
    description="Adds an Activity to the Actor's Inbox. (stub implementation).",
    status_code=status.HTTP_202_ACCEPTED,
    response_class=Response,
    operation_id="actors_post_inbox",
)
def post_actor_inbox(
    actor_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    delivery: VerifiedDelivery = Depends(verified_delivery),
    dl: DataLayer = Depends(get_actor_dl),
) -> None:
    """Adds an item to the Actor's Inbox.
    The 202 Accepted status code indicates that the request has been accepted for
    processing, but the processing has not been completed. This is appropriate here
    because the inbox processing is handled asynchronously in the background.
    The 202 carries no body (IE-08-001): nothing is known yet beyond acceptance,
    and the sender already holds the activity's id.

    Policy logic lives in ``process_payload`` (core BT module); this
    endpoint is thin glue that supplies adapter implementations and
    schedules the background task (IO-03-003).

    It answers at ``/inbox``, the address a hosted actor's profile names
    (``hosted_endpoints``) and a sender holding that profile posts to
    (OX-12-009), as well as at ``/inbox/``.

    The ingress stages run in order: the body is decoded and its proofs
    verified (``verified_delivery``, SIG-03-003), then it is parsed
    (``parse_activity``) and its addressing checked (IE-11-001).  The
    background task gets the verified body, not the parsed activity, and
    parses it again in its own ingress: an inbox run starts only from a body
    (``FastAPIIngressAdapter.parse``).

    Args:
        actor_id: The ID of the Actor whose Inbox to add the item to.
        request: The FastAPI Request (used to resolve the per-app emitter/dispatcher).
        delivery: The verified body and its addressed actor (the
            ``verified_delivery`` dependency).
        background_tasks: FastAPI BackgroundTasks instance to schedule background tasks.
    Returns:
        None
    Raises:
        HTTPException: If the Actor is not found, the body is refused by
            the verification stage, or it does not parse.
    """
    canonical_actor_id = delivery.receiver.id_
    activity = parse_activity(delivery.body)

    if not _activity_addressed_to(activity, canonical_actor_id):
        logger.warning(
            "Activity %s is not addressed to actor %s; refusing (IE-11-001).",
            activity.id_,
            canonical_actor_id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Activity is not addressed to actor {canonical_actor_id}.",
        )

    emitter = getattr(request.app.state, "emitter", None)
    dispatcher = getattr(request.app.state, "dispatcher", None)

    background_tasks.add_task(
        run_inbox_pipeline,
        delivery.body,
        dl,
        canonical_actor_id,
        dispatcher,
        emitter,
    )


@router.post(
    "/{actor_id:path}/outbox/",
    summary="Add an Activity to the Actor's Outbox.",
    description="Adds an Activity to the Actor's Outbox. (stub implementation).",
    status_code=status.HTTP_200_OK,
    operation_id="actors_post_outbox",
)
def post_actor_outbox(
    actor_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    body: Annotated[dict[str, Any], Body()],
    dl: DataLayer = Depends(get_actor_dl),
) -> None:
    """Adds an item to the Actor's Outbox.

    The body is parsed by the wire parser, as the inbox parses one, so the
    activity keeps its own type and every field it carries (its ``object``
    and ``target`` included); validating it as the bare ``as_Activity``
    would drop them.

    Args:
        actor_id: The ID of the Actor whose Outbox to add the item to.
        body: The Activity to add to the Outbox, as JSON.
        request: The FastAPI Request (used to resolve the per-app emitter).
        background_tasks: FastAPI BackgroundTasks instance to schedule background tasks.
    Returns:
        None
    Raises:
        HTTPException: If the Actor is not found.
    """
    actor = _resolve_actor_or_404(actor_id, dl)
    canonical_actor_id = actor.id_
    activity = parse_activity(body)

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
        "Posting activity to actor %s outbox: %s", canonical_actor_id, activity
    )

    # No clone: the injected DataLayer already is this actor's store.
    actor_dl = cast(Any, dl)
    # Sealing signs the body (SIG-01-001); one the signer refuses is answered
    # 422 and, the transaction rolled back, leaves nothing stored or queued.
    try:
        with actor_dl.transaction():
            # A case activity states this actor's ledger tail and, sent to the
            # CASE_MANAGER, its next sender sequence, as one its own adapter
            # builds does (SYNC-18-001, SYNC-21-001); one that states them keeps
            # them.  One transaction, so the number is used exactly when the
            # body carrying it is sealed and queued (SYNC-21-003).
            activity = with_outbound_stamps(actor_dl, activity)
            actor_dl.create(object_to_record(activity))
            # Seal what was posted: the outbox delivers this body, not a re-read
            # of the record (VM-08-003).
            seal_outbound_body(actor_dl, activity)
            actor_dl.outbox_append(activity.id_)
    except VultronUnsignableJsonError as error:
        raise unsignable_http_exception(str(error)) from error

    emitter = getattr(request.app.state, "emitter", None)
    # Keyword, not positional: `outbox_handler`'s third parameter used to be a
    # second DataLayer (the shared one), so a positional third argument reads as
    # a store here and silently becomes the emitter.  See the ratchet in
    # test/architecture/test_outbox_handler_emitter_keyword.py.
    background_tasks.add_task(
        outbox_handler, canonical_actor_id, actor_dl, emitter=emitter
    )
