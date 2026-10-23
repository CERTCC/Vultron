#!/usr/bin/env python
"""
Vultron API v2 Routers
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
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

from fastapi import APIRouter, Request

from vultron.adapters.driving.fastapi.routers import (
    actors,
    datalayer,
    examples,
    health,
    info,
    trigger_actor,
    trigger_case,
    trigger_embargo,
    trigger_report,
)

router = APIRouter()


@router.get("/version", tags=["Version"], operation_id="version_get")
def get_version(request: Request):
    """Returns the current version of the Vultron API."""
    return {"version": request.app.version}


# Order matters, and this pair is the reason.
#
# The actors router serves `GET /actors/{actor_id:path}`, and the `:path`
# converter is greedy — it matches slashes.  The debug/inspection router now
# lives under `/actors/{actor_id}/datalayer/...` (ADR-0073 moved it there when
# the unscoped `/datalayer/...` view was deleted).  Starlette matches in
# registration order, so with the actors router first, a request for
# `/actors/vendor/datalayer/urn:uuid:x` matched `GET /actors/{actor_id:path}`
# with `actor_id = "vendor/datalayer/urn:uuid:x"` and answered
# `404 Actor not found` — indistinguishable from a genuinely missing actor,
# which is why every route in the datalayer router was unreachable without
# anything looking broken.
#
# The specific prefix therefore goes first.  Its `{actor_id}` is deliberately
# *not* a `:path`: a path segment is resolved to a canonical URI by computation
# (ADR-0073#url-segment-computed-not-looked-up), so a single segment is the addressable form.
# See test/adapters/driving/fastapi/routers/test_datalayer_route_reachable.py.
router.include_router(datalayer.router)
router.include_router(datalayer.admin_router)

router.include_router(actors.router)

router.include_router(examples.router)

router.include_router(health.router)

router.include_router(info.router)

router.include_router(trigger_report.router)

router.include_router(trigger_actor.router)

router.include_router(trigger_case.router)

router.include_router(trigger_embargo.router)
