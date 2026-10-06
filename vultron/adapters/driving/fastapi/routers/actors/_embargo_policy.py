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
returns the record the profile carries inline (EP-02-001, EP-02-002).  Because
a publish rewrites the whole profile, its write is a compare-and-set against
the profile it read, so a concurrent profile update is never silently
overwritten (EP-02-004).

The routes are included by :mod:`._routes` *ahead of* its ``GET
/{actor_id:path}`` catch-all, which would otherwise swallow the path.
"""

import logging
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, field_validator

from vultron.adapters.driving.fastapi.deps import get_actor_dl
from vultron.adapters.driving.fastapi.errors import conflict_http_exception
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
from vultron.errors import VultronError

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


_PUBLISH_ATTEMPTS = 3
"""How many times a PUT re-reads the profile before refusing with 409 (EP-02-004)."""


class ProfileChangedError(VultronError):
    """The actor's profile changed between this publish's read and its write."""


def publish_embargo_policy(
    dl: DataLayer, actor: CoreActor, terms: EmbargoPolicyPublishRequest
) -> tuple[EmbargoPolicy, bool]:
    """Publish *terms* as *actor*'s ``EmbargoPolicy`` on its own profile.

    ``actor_id`` and ``inbox`` come from the actor's record (EP-01-005); the
    record's own validator has already derived a blank ``inbox`` from its id,
    so nothing is manufactured here.

    The policy is written into the profile's ``embargo_policy`` field and the
    profile is saved to *dl*, the actor's own store (EP-01-004).  An actor has
    one profile and the profile one policy field, so a replace overwrites the
    field and exactly one policy exists for the actor with nothing to delete
    (EP-01-001, EP-02-005).

    *actor* is the profile as the caller read it, and the write is a
    compare-and-set against it (:meth:`DataLayer.save_if_unchanged`): the
    whole profile is rewritten, so a plain save would overwrite any update
    another writer made since the read (EP-02-004, #4102).

    Returns:
        The stored policy and whether it *replaced* an earlier one.

    Raises:
        ProfileChangedError: The stored profile is no longer *actor*; nothing
            was written.
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
    if not dl.save_if_unchanged(updated, expected=actor):
        raise ProfileChangedError(
            f"Actor {actor.id_!r}'s profile changed while its embargo policy"
            " was being published"
        )
    return policy, replaced


def _publish_on_a_current_read(
    dl: DataLayer, actor_id: str, terms: EmbargoPolicyPublishRequest
) -> tuple[CoreActor, EmbargoPolicy, bool]:
    """Read the profile and publish *terms* on it, re-reading if it went stale.

    A publish whose read was overtaken by another write is re-applied to a
    fresh read, so the concurrent update is kept rather than overwritten.
    After :data:`_PUBLISH_ATTEMPTS` stale reads the request is refused with
    409 and nothing is written (EP-02-004, #4102).

    Returns:
        The profile the policy was published on, the policy, and whether it
        replaced an earlier one.

    Raises:
        HTTPException: 404 for an actor this node does not host; 409 when
            every attempt found the profile changed.
    """
    resolved_id = actor_id
    for attempt in range(1, _PUBLISH_ATTEMPTS + 1):
        actor = _resolve_actor_or_404(actor_id, dl)
        resolved_id = actor.id_
        try:
            policy, replaced = publish_embargo_policy(dl, actor, terms)
        except ProfileChangedError:
            # A stale read is the designed recovery path: INFO, not WARNING.
            logger.info(
                "Actor %s embargo policy publish attempt %d/%d found the"
                " profile changed since it was read",
                actor.id_,
                attempt,
                _PUBLISH_ATTEMPTS,
            )
            continue
        return actor, policy, replaced
    # Every attempt was overtaken: the client sees a refusal.
    logger.warning(
        "Actor %s embargo policy publish refused with 409 after %d stale"
        " reads; nothing was written",
        resolved_id,
        _PUBLISH_ATTEMPTS,
    )
    raise conflict_http_exception(
        f"The profile of actor {resolved_id!r} changed under each of"
        f" {_PUBLISH_ATTEMPTS} attempts to publish its embargo"
        " policy; nothing was written. Retry the request."
    )


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
        "calendar-unit duration; 409 when the actor's profile kept changing "
        "under the request, in which case nothing was written."
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
    answers; :func:`publish_embargo_policy` holds the replace semantics and
    :func:`_publish_on_a_current_read` the retry-then-409 on a concurrent
    profile write (EP-02-004).
    """
    actor, policy, replaced = _publish_on_a_current_read(
        datalayer, actor_id, body
    )
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
