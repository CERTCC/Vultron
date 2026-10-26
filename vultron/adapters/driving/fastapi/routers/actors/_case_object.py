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

"""``GET /actors/{actor_id}/case-object``: the case host's object read.

A replica that does not hold an object a case names fetches it here, from the
case's CASE_MANAGER (AKM-05-006, AKM-05-007, ADR-0107).  The requester names
itself in the :data:`~vultron.adapters.driven.http_object_fetch.REQUESTER_HEADER`
header; the prototype trusts that claim as its inbox trusts a claimed sender,
and authenticates nobody (#509).
"""

import logging
from typing import cast

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from vultron.adapters.driven import actor_hosts
from vultron.adapters.driven.http_object_fetch import REQUESTER_HEADER
from vultron.adapters.driving.fastapi.deps import get_actor_dl, node_base_url
from vultron.adapters.driving.fastapi.responses import AS2JSONResponse
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.datalayer import DataLayer
from vultron.core.services.dereference import case_object_for_participant
from vultron.errors import (
    VultronNotACaseParticipantError,
    VultronNotFoundError,
)

logger = logging.getLogger("uvicorn.error")

router = APIRouter()


@router.get(
    "/{actor_id:path}/case-object",
    summary="Get a Case Object for a Case Participant",
    description=(
        "Returns an object a case names, as the case's CASE_MANAGER holds"
        " it, to an active participant of that case (object dereference,"
        " AKM-05-006). The requester names itself in the"
        f" `{REQUESTER_HEADER}` header; the prototype trusts that claim as"
        " its inbox trusts a claimed sender, and authenticates nobody"
        " (#509)."
    ),
    operation_id="actors_get_case_object",
)
def get_case_object(
    actor_id: str,
    case_id: str,
    object_id: str,
    request: Request,
    requester: str | None = Header(default=None, alias=REQUESTER_HEADER),
    dl: DataLayer = Depends(get_actor_dl),
) -> AS2JSONResponse:
    """Serve *object_id* of *case_id* to the participant the request names.

    404 when this actor does not host the case, or the case does not name
    the object; 403 when the requester is no active participant of the
    case; 401 when the request names no requester.
    """
    if not requester:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"The request names no requester ({REQUESTER_HEADER}).",
        )
    host_id = actor_hosts.canonical_actor_uri(
        actor_id, base_url=node_base_url(request)
    )
    try:
        found = case_object_for_participant(
            cast(CasePersistence, dl), host_id, case_id, object_id, requester
        )
    except VultronNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except VultronNotACaseParticipantError as exc:
        logger.warning(
            "case object read refused: %s (case_id=%s, object_id=%s)",
            exc,
            case_id,
            object_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    return AS2JSONResponse(found)
