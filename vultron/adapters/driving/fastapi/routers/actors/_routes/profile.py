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

from typing import Any, cast

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
    _actor_class_for_record,
    _find_actor_record,
)
from vultron.adapters.utils import full_object_id, strip_id_prefix
from vultron.core.models.actor import (
    CoreActor,
    endpoint_uri,
    hosted_endpoints,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.datalayer import DataLayer
from vultron.core.use_cases.query.action_rules import (
    ActionRulesRequest,
    GetActionRulesUseCase,
)
from vultron.errors import VultronNotFoundError, VultronValidationError
from vultron.wire.as2 import signing

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
    return AS2JSONResponse(_published_profile(datalayer, actor_id))


def _published_profile(datalayer: DataLayer, actor_id: str) -> dict[str, Any]:
    """The profile the actor *actor_id* names publishes from its own store.

    :func:`_find_actor_record` returns only the actor the request addresses,
    from that actor's own store, never a peer's record (ADR-0073), so the
    actor served is the one this node hosts.  It publishes what only it
    knows: the endpoints this node routes for it, which a record created
    before it stated them may lack (ISSUE-3616), and the key it signs with.

    Raises:
        HTTPException: 404 when the store holds no such actor (AR-10-002).
    """
    actor_record = _find_actor_record(datalayer, actor_id)
    if not actor_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Actor not found."
        )

    actor_cls = _actor_class_for_record(actor_record)
    as_actor = _with_own_key(
        cast(Any, actor_cls.model_validate(actor_record.get("data_", {})))
    )
    profile: dict[str, Any] = as_actor.model_dump(
        mode="json", by_alias=True, exclude_none=True
    )
    own = hosted_endpoints(as_actor.id_)
    for field_name in ("inbox", "outbox"):
        profile[field_name] = (
            endpoint_uri(getattr(as_actor, field_name, None))
            or own[field_name]
        )
    return profile


def _with_own_key(actor: CoreActor) -> CoreActor:
    """*actor*, the actor this node hosts, listing the key it signs with.

    The published key is always the one the actor's proofs are made with,
    so a key a stored record happens to state is replaced rather than
    served: a profile naming any other key would make every proof the
    actor sends fail to verify.  Only the key's owner computes its seeded
    key (SIG-05-001, SIG-05-002), and only the public half is published
    (ENC-01-007).
    """
    key = signing.seeded_signing_key(actor.id_)
    published = actor.model_copy()
    # Assignment, not ``model_copy(update=...)``: it re-runs the actor's
    # validators, which refuse a key another actor controls (CM-27-001).
    published.assertion_method = [signing.published_multikey(key, actor.id_)]
    return published


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
    return AS2JSONResponse(_published_profile(datalayer, actor_id))
