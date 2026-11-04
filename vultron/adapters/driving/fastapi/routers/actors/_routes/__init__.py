#!/usr/bin/env python
"""
Route handlers for the Vultron FastAPI actors router.

Defines the ``/actors`` APIRouter and assembles its endpoints from focused
submodules, in registration order:

- ``registry`` — list actors, create a hosted actor, register a peer
- ``profile`` — actor profile and CVD action rules
- ``mailbox`` — the inbox delivery target and the outbox post
- the embargo-policy and case-object routers
- ``profile.catch_all_router`` — ``GET /{actor_id:path}``, last

Route-level dependencies and business logic delegated to ``_lookup`` and
``_inbox`` helpers; no direct DataLayer manipulation here beyond what FastAPI
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

from fastapi import APIRouter

from vultron.adapters.driving.fastapi.routers.actors import (
    _case_object,
    _embargo_policy,
)
from vultron.adapters.driving.fastapi.routers.actors._routes import (
    mailbox,
    profile,
    registry,
)
from vultron.adapters.driving.fastapi.routers.actors._routes.mailbox import (
    post_actor_inbox,
    post_actor_outbox,
    refuse_non_post_inbox,
)
from vultron.adapters.driving.fastapi.routers.actors._routes.profile import (
    get_action_rules,
    get_actor,
    get_actor_profile,
)
from vultron.adapters.driving.fastapi.routers.actors._routes.registry import (
    ActorCreateRequest,
    AnyActor,
    PeerRegisterRequest,
    create_actor,
    get_actors,
    register_peer,
)

# Each submodule's router carries the ``/actors`` prefix and the tag itself,
# so every route keeps the path and tags it was declared with; the two
# sibling routers get them at inclusion, as they did before the split.
router = APIRouter()
router.include_router(registry.router)
router.include_router(profile.router)
router.include_router(mailbox.router)
# Included ahead of the catch-all below on purpose: FastAPI matches routes in
# registration order, and ``GET /{actor_id:path}`` would otherwise claim
# ``/actors/{slug}/embargo-policy`` and ``/actors/{slug}/cases/{key}/objects``
# with the suffix folded into the segment.
router.include_router(
    _embargo_policy.router, prefix="/actors", tags=["Actors"]
)
router.include_router(_case_object.router, prefix="/actors", tags=["Actors"])
router.include_router(profile.catch_all_router)

__all__ = [
    "ActorCreateRequest",
    "AnyActor",
    "PeerRegisterRequest",
    "create_actor",
    "get_action_rules",
    "get_actor",
    "get_actor_profile",
    "get_actors",
    "post_actor_inbox",
    "post_actor_outbox",
    "refuse_non_post_inbox",
    "register_peer",
    "router",
]
