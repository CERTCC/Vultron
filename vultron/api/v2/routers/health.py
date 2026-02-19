#!/usr/bin/env python
"""
Health check endpoints for the Vultron API.

Implements OB-05-001 (/health/live) and OB-05-002 (/health/ready)
from specs/observability.md.
"""

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

from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/live")
async def liveness():
    """Returns 200 if the process is running (OB-05-001)."""
    return {"status": "ok"}


@router.get("/ready")
async def readiness():
    """Returns 200 if the service is ready to accept requests (OB-05-002)."""
    return {"status": "ok"}
