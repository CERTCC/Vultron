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

"""``GET`` and ``PUT /actors/{actor_id}/embargo-policy`` (EP-02).

An actor's published ``EmbargoPolicy`` is its **actor default**: the standing
embargo proposal that competes under shortest-wins when a case is created for
a report it receives (EP-04-003, EP-04-010).  ``owner_embargo_policies`` reads
that policy from the owner's own store, so publishing one is a write to that
store and nothing else — which is why this lives on the actors router under the
per-actor store dependency (ADR-0073) rather than on a shared admin surface.

``PUT`` publishes (creates or replaces) the policy for a hosted actor; ``GET``
returns the published record (EP-02-001).  The actor profile lists the
endpoint URL under ``embargo_policy`` once one is published (EP-02-002).

The routes are included by :mod:`._routes` *ahead of* its ``GET
/{actor_id:path}`` catch-all, which would otherwise swallow the path.
"""

import logging
from datetime import timedelta
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, field_validator

from vultron.adapters.driving.fastapi.deps import get_actor_dl
from vultron.adapters.driving.fastapi.responses import AS2JSONResponse
from vultron.adapters.driving.fastapi.routers.actors._lookup import (
    _resolve_actor_or_404,
)
from vultron.core.models.actor import CoreActor
from vultron.core.models.base import NonEmptyString
from vultron.core.models.embargo_policy import EmbargoPolicy, parse_duration
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.datalayer import DataLayer
from vultron.core.services.embargo_duration import (
    owner_embargo_policies,
    select_actor_default_policy,
)
from vultron.enums.object_types import VultronObjectType

logger = logging.getLogger("uvicorn.error")

router = APIRouter()

EMBARGO_POLICY_PATH_SUFFIX = "embargo-policy"


def embargo_policy_url(actor_id: str) -> str:
    """The URL an actor's profile lists for its embargo policy (EP-02-002)."""
    return f"{actor_id}/{EMBARGO_POLICY_PATH_SUFFIX}"


def _duration(value: Any) -> timedelta | None:
    """Parse an ISO 8601 duration for a request field, refusing calendar units.

    ``parse_duration`` raises ``TypeError`` for a value that is neither a
    string nor a ``timedelta``; pydantic reports only ``ValueError`` as a
    validation failure, so the type complaint is re-raised as one and reaches
    the client as 422 rather than 500 (HTTP-03-009).
    """
    try:
        return parse_duration(value)
    except TypeError as exc:
        raise ValueError(str(exc)) from exc


class EmbargoPolicyPublishRequest(BaseModel):
    """Body of ``PUT /actors/{actor_id}/embargo-policy``.

    Carries the terms only (EP-01-002, EP-01-003).  ``actor_id`` and ``inbox``
    are not accepted: the policy applies to the actor named in the path, and
    both are derived from its own record so a body cannot publish terms in
    another actor's name (EP-01-005).
    """

    model_config = ConfigDict(extra="forbid")

    preferred_duration: timedelta
    minimum_duration: timedelta | None = None
    maximum_duration: timedelta | None = None
    notes: NonEmptyString | None = None

    @field_validator(
        "preferred_duration",
        "minimum_duration",
        "maximum_duration",
        mode="before",
    )
    @classmethod
    def _parse_iso8601_duration(cls, value: Any) -> timedelta | None:
        return _duration(value)


def publish_embargo_policy(
    dl: DataLayer, actor: CoreActor, terms: EmbargoPolicyPublishRequest
) -> tuple[EmbargoPolicy, bool]:
    """Publish *terms* as *actor*'s ``EmbargoPolicy`` in *dl*, its own store.

    ``actor_id`` and ``inbox`` come from the actor's record (EP-01-005); the
    record's own validator has already derived a blank ``inbox`` from its id,
    so nothing is manufactured here.  Exactly one policy remains for the
    actor: the new record is written first, then every earlier one is
    deleted, so a failure between the two leaves the actor with a policy
    rather than none, and ``owner_embargo_policies`` cannot hand shortest-wins
    a superseded default (EP-04-010).  The actor record then lists the
    endpoint URL under ``embargo_policy`` (EP-02-002).

    Returns:
        The stored policy and whether it *replaced* an earlier one.
    """
    previous = owner_embargo_policies(_case_store(dl), actor.id_)
    policy = EmbargoPolicy(
        actor_id=actor.id_,
        inbox=actor.inbox,
        preferred_duration=terms.preferred_duration,
        minimum_duration=terms.minimum_duration,
        maximum_duration=terms.maximum_duration,
        notes=terms.notes,
    )
    dl.create(policy)
    for stale in previous:
        if stale.id_ != policy.id_:
            dl.delete(VultronObjectType.EMBARGO_POLICY.value, stale.id_)

    listed = embargo_policy_url(actor.id_)
    if actor.embargo_policy != listed:
        actor.embargo_policy = listed
        dl.save(actor)
    return policy, bool(previous)


def _published_policy(dl: DataLayer, actor_id: str) -> EmbargoPolicy | None:
    """The policy *actor_id* has published in *dl*, or ``None``.

    Read through the same selection the case-creation tree applies
    (EP-04-010), so what this endpoint shows is what shortest-wins would use.
    """
    return select_actor_default_policy(
        owner_embargo_policies(_case_store(dl), actor_id)
    )


def _case_store(dl: DataLayer) -> CasePersistence:
    """View the actor's store through the narrow port the policy helpers take.

    ``get_actor_dl`` types the store as the broad ``DataLayer``; the concrete
    ``SqliteDataLayer`` it hands out satisfies ``CasePersistence`` too, and
    ``owner_embargo_policies`` needs only ``list_objects`` from it (DL-04).
    """
    return cast(CasePersistence, dl)


@router.get(
    "/{actor_id:path}/" + EMBARGO_POLICY_PATH_SUFFIX,
    summary="Get Actor Embargo Policy",
    description=(
        "Returns the embargo policy this actor has published — its actor "
        "default under shortest-wins (EP-04-003). 404 when none is published."
    ),
    operation_id="actors_get_embargo_policy",
    response_model=EmbargoPolicy,
)
def get_embargo_policy(
    actor_id: str, datalayer: DataLayer = Depends(get_actor_dl)
):
    """Return the published ``EmbargoPolicy`` for a hosted actor (EP-02-001)."""
    actor = _resolve_actor_or_404(actor_id, datalayer)
    policy = _published_policy(datalayer, actor.id_)
    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Actor {actor.id_!r} has not published an embargo policy.",
        )
    return AS2JSONResponse(policy)


@router.put(
    "/{actor_id:path}/" + EMBARGO_POLICY_PATH_SUFFIX,
    summary="Publish Actor Embargo Policy",
    description=(
        "Publishes (creates or replaces) the embargo policy for a hosted "
        "actor, in that actor's own store. The policy's actor id and inbox are "
        "derived from the actor record. 201 on first publish, 200 on replace; "
        "404 for an actor this node does not host; 422 for a malformed or "
        "calendar-unit duration."
    ),
    operation_id="actors_put_embargo_policy",
    response_model=EmbargoPolicy,
)
def put_embargo_policy(
    actor_id: str,
    body: EmbargoPolicyPublishRequest,
    datalayer: DataLayer = Depends(get_actor_dl),
):
    """Publish *body* as the hosted actor's ``EmbargoPolicy`` (EP-01-004).

    The handler resolves the actor (404 when this node does not host it) and
    answers; :func:`publish_embargo_policy` holds the replace semantics.
    """
    actor = _resolve_actor_or_404(actor_id, datalayer)
    policy, replaced = publish_embargo_policy(datalayer, actor, body)
    logger.info(
        "Actor %s published embargo policy %s (preferred %s, %s)",
        actor.id_,
        policy.id_,
        policy.preferred_duration,
        "replaced an earlier one" if replaced else "first publish",
    )
    return AS2JSONResponse(
        policy,
        status_code=(
            status.HTTP_200_OK if replaced else status.HTTP_201_CREATED
        ),
    )
