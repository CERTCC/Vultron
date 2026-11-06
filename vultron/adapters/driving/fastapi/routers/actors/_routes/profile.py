"""Actor read routes: profile, CVD action rules, and the actor catch-all.

``get_actor`` answers the path catch-all ``/{actor_id:path}``, so it is
registered on its own router, :data:`catch_all_router`, which the package
includes after every other actor route.
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

from typing import cast

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from vultron.adapters.driven import actor_hosts
from vultron.adapters.driving.fastapi.deps import (
    get_actor_dl,
)
from vultron.adapters.driving.fastapi.responses import AS2JSONResponse
from vultron.adapters.driving.fastapi.routers.actors._lookup import (
    published_profile,
)
from vultron.adapters.utils import full_object_id, strip_id_prefix
from vultron.core.models.case import VulnerabilityCase
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.datalayer import DataLayer
from vultron.core.use_cases.query.action_rules import (
    ActionRulesRequest,
    GetActionRulesUseCase,
)
from vultron.errors import VultronNotFoundError, VultronValidationError

router = APIRouter(prefix="/actors", tags=["Actors"])

# Registered last by the package: FastAPI matches routes in registration order,
# and ``GET /{actor_id:path}`` would otherwise claim every longer actor path.
catch_all_router = APIRouter(prefix="/actors", tags=["Actors"])


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

    Includes actor metadata (name, type), inbox URL, outbox URL, the
    ``Multikey`` that verifies the actor's proofs under ``assertionMethod``
    (ENC-01-002), and any other ActivityStreams profile fields present on
    the actor.  Intended for use by remote systems discovering how to
    interact with this actor, so it needs no proof or signature
    (SIG-02-002).  The `inbox` and `outbox` fields are returned as URL
    strings, not embedded collection objects.
    """
    return AS2JSONResponse(published_profile(datalayer, actor_id))


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
        actor_obj = dl.read(canonical) or dl.read(full_object_id(actor_id))
        case_obj = dl.read(case_id)
        if case_obj is None or not isinstance(case_obj, VulnerabilityCase):
            case_obj = dl.find_case_by_short_id(case_id)
        if case_obj is None or not isinstance(case_obj, VulnerabilityCase):
            raise VultronNotFoundError("VulnerabilityCase", case_id)  # noqa: TRY301  # ruff-baseline #3353
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
        return (
            GetActionRulesUseCase(dl=cast(CasePersistence, dl), request=req)
            .execute()
            .model_dump(mode="json")
        )
    except VultronNotFoundError as exc:
        raise HTTPException(  # noqa: B904  # ruff-baseline #3353
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except VultronValidationError as exc:
        raise HTTPException(  # noqa: B904  # ruff-baseline #3353
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        )


@catch_all_router.get(
    "/{actor_id:path}",
    description="Returns an Actor by surrogate key or canonical ID.",
    operation_id="actors_get",
)
def get_actor(actor_id: str, datalayer: DataLayer = Depends(get_actor_dl)):
    """Returns an Actor by actor_id.

    Accepts either a canonical actor ID or the actor's surrogate key.  The
    actor's id dereferences to the same profile ``/profile`` serves, so a
    verifier that fetches the document a proof's key id names finds the key
    there (SIG-02-001).
    """
    return AS2JSONResponse(published_profile(datalayer, actor_id))
