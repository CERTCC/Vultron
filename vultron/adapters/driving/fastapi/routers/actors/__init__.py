#!/usr/bin/env python
"""
Vultron FastAPI actors router package.

Provides the ``/actors`` APIRouter and all related helpers, split into
focused submodules:

- ``_lookup``  — actor-record lookup helpers (no route handlers)
- ``_inbox``   — inbox processing helpers (no route handlers)
- ``_routes``  — APIRouter and all ``@router.*`` endpoint handlers

Public surface (used by ``v2_router`` and tests):
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

from vultron.adapters.driving.fastapi.routers.actors._routes import (  # noqa: F401
    ActorCreateRequest,
    AnyActor,
    router,
)

# Re-exported so tests can key dependency_overrides off the package rather than
# the private _routes module (issue #970).  This is now the actor-scoping seam:
# get_shared_dl is gone, since no DataLayer is unscoped (ADR-0071).
from vultron.adapters.driving.fastapi.deps import get_actor_dl  # noqa: F401
