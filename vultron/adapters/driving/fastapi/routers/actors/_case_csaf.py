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
"""``GET /actors/{actor_id}/cases/{case_key}/csaf``: the operator's CSAF read.

Returns the CSAF projection of a case from the addressed actor's own
replica, cut by the joined profile and rendered with ``tracking.status``
``interim``, because the case continues to change (ADR-0219).  The operator
gives the document to a party outside Vultron out of band.

The read writes nothing: no DataLayer write, no ledger entry and no
activity (CSAF-06-013).  The case is named in the path by its id or by its
surrogate key, as the case-object route names it.

The document is the joined profile's cut, labelled ``AMBER+STRICT``, and
the route checks no requester: HTTP-level request authentication is not
built yet (#509), so a deployment must not expose it to anyone but the
operator.
"""

import logging
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from vultron.adapters.driven import actor_hosts
from vultron.adapters.driven.case_projection import CsafProjectionAdapter
from vultron.adapters.driving.fastapi.case_reference import find_case
from vultron.adapters.driving.fastapi.deps import get_actor_dl, node_base_url
from vultron.core.models.case_projection import PublicationStatus
from vultron.core.models.case_projection_profile import JOINED_PROFILE
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.datalayer import DataLayer
from vultron.core.services.case_projection import (
    PROJECTION_FAILURES,
    project_case,
)

logger = logging.getLogger("uvicorn.error")

router = APIRouter()

#: The renderer this route projects through: CSAF, the port's first format.
_CSAF = CsafProjectionAdapter()


@router.get(
    "/{actor_id:path}/cases/{case_key}/csaf",
    summary="Get a CSAF Projection of a Case",
    description=(
        "Returns a CSAF 2.1 document projected from the actor's replica of"
        " the case: the joined profile's cut, with tracking status"
        " `interim` (ADR-0219). The operator hands it to a party outside"
        " Vultron; the read writes nothing, adds no ledger entry and sends"
        " no activity. HTTP-level request authentication is not built yet"
        " (#509): any caller that reaches the route gets the document."
    ),
    operation_id="actors_get_case_csaf",
)
def get_case_csaf(
    actor_id: str,
    case_key: str,
    request: Request,
    dl: DataLayer = Depends(get_actor_dl),
) -> JSONResponse:
    """The joined CSAF projection of the case *case_key* names.

    *case_key* is the case's full id, or its surrogate key.  404 when this
    actor holds no such case, or the key matches more than one; 409 when
    the replica holds the case but cannot be projected, such as one that
    lacks the ledger entry at the case's position, which a later sync
    supplies (every :data:`PROJECTION_FAILURES` but a missing case).
    """
    case = find_case(case_key, dl)
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"This actor holds no case '{case_key}'.",
        )
    projector_id = actor_hosts.canonical_actor_uri(
        actor_id, base_url=node_base_url(request)
    )
    try:
        document = project_case(
            cast(CasePersistence, dl),
            case.id_,
            projector_id,
            JOINED_PROFILE,
            PublicationStatus.INTERIM,
            _CSAF,
        )
    except PROJECTION_FAILURES as exc:
        logger.warning(
            "CSAF projection refused: %s (case_id=%s, actor_id=%s)",
            exc,
            case.id_,
            projector_id,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    logger.debug(
        "CSAF projection served (case_id=%s, actor_id=%s, profile=%s)",
        case.id_,
        projector_id,
        JOINED_PROFILE.name,
    )
    return JSONResponse(document)
