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
a report it receives (EP-04-003, EP-04-010).  The policy is a field of the
actor's own profile record (EP-01-001, EP-01-004), not a separate object:
publishing one rewrites that record in the actor's own store, and the profile
then carries the terms wherever it travels — inline on every
``Create(CaseProposal)`` the actor sends, which is the only place a
CASE_MANAGER reads the default from (CP-01-010).  That is why this lives on
the actors router under the per-actor store dependency (ADR-0073) rather than
on a shared admin surface.

``PUT`` publishes (creates or replaces) the policy for a hosted actor; ``GET``
returns the record the profile carries inline (EP-02-001, EP-02-002).

The routes are included by :mod:`._routes` *ahead of* its ``GET
/{actor_id:path}`` catch-all, which would otherwise swallow the path.
"""

import logging
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, field_validator

from vultron.adapters.driving.fastapi.deps import get_actor_dl
from vultron.adapters.driving.fastapi.responses import AS2JSONResponse
from vultron.adapters.driving.fastapi.routers.actors._lookup import (
    _resolve_actor_or_404,
)
from vultron.core.models.actor import CoreActor
from vultron.core.models.base import NonEmptyString
from vultron.core.models.embargo_policy import (
    EMBARGO_POLICY_PATH_SUFFIX,
    EmbargoPolicy,
    parse_duration,
)
from vultron.core.ports.datalayer import DataLayer

logger = logging.getLogger("uvicorn.error")

router = APIRouter()


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
    """Publish *terms* as *actor*'s ``EmbargoPolicy`` on its own profile.

    ``actor_id`` and ``inbox`` come from the actor's record (EP-01-005); the
    record's own validator has already derived a blank ``inbox`` from its id,
    so nothing is manufactured here.

    The policy is written into the profile's ``embargo_policy`` field and the
    profile is saved to *dl*, the actor's own store (EP-01-004).  An actor has
    one profile and the profile one policy field, so a replace — the next
    request or a concurrent one — overwrites the field and exactly one policy
    exists for the actor with nothing to delete (EP-01-001, EP-02-003).

    Returns:
        The stored policy and whether it *replaced* an earlier one.
    """
    replaced = actor.embargo_policy is not None
    policy = EmbargoPolicy(
        id_=EmbargoPolicy.build_id(actor.id_),
        actor_id=actor.id_,
        inbox=actor.inbox,
        preferred_duration=terms.preferred_duration,
        minimum_duration=terms.minimum_duration,
        maximum_duration=terms.maximum_duration,
        notes=terms.notes,
    )
    # Re-validated, not ``model_copy(update=...)``: the profile's own
    # validator is what holds the policy to this actor (EP-01-001).
    updated = type(actor).model_validate(
        {**dict(actor), "embargo_policy": policy}
    )
    dl.save(updated)
    return policy, replaced


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
    """Return the hosted actor's profile ``embargo_policy`` (EP-02-001/002)."""
    actor = _resolve_actor_or_404(actor_id, datalayer)
    policy = actor.embargo_policy
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
