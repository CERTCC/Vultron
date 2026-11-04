#!/usr/bin/env python

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
"""
Provides a backend API router for basic Vultron data layer operations.

Grouped by concern (CS-18-005): ``routes`` holds the actor-scoped read routes,
``admin`` the node-level ``admin_router`` and ``stored`` their read helpers.
"""

from vultron.adapters.driving.fastapi.routers.datalayer.admin import (
    admin_router,
    reset_datalayer,
)
from vultron.adapters.driving.fastapi.routers.datalayer.routes import (
    get_actor_offer,
    get_actor_outbox,
    get_actors,
    get_datalayer_contents,
    get_object,
    get_object_by_key,
    get_objects,
    get_offer,
    get_offers,
    get_report,
    get_reports,
    router,
)

__all__ = [
    "admin_router",
    "get_actor_offer",
    "get_actor_outbox",
    "get_actors",
    "get_datalayer_contents",
    "get_object",
    "get_object_by_key",
    "get_objects",
    "get_offer",
    "get_offers",
    "get_report",
    "get_reports",
    "reset_datalayer",
    "router",
]
