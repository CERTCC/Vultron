#!/usr/bin/env python

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

"""
Trigger router for actor-level participant behaviors.

Thin wrapper: validates the HTTP body, builds the verb's core request and hands
it to :func:`~vultron.adapters.driving.fastapi.trigger_runner.run_trigger`,
which drains the *emitting* actor's outbox for a delegated emit (CM-24-001).
All domain logic lives in vultron.core.use_cases.triggers.actor.

The routes are grouped by concern, one submodule each
(:mod:`.invitations`, :mod:`.recommendations`, :mod:`.ownership`), and
included here in that order, so the OpenAPI route order is unchanged.
Each submodule's router carries the ``/actors`` prefix and the ``Triggers``
tag itself, so every route leaf holds its full path.
"""

from fastapi import APIRouter

from . import invitations, ownership, recommendations

__all__ = ["router"]

router = APIRouter()
router.include_router(invitations.router)
router.include_router(recommendations.router)
router.include_router(ownership.router)
