#!/usr/bin/env python
"""
Handler for Reject Activities
"""
#  Copyright (c) 2025 Carnegie Mellon University and Contributors.
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

import logging
from functools import partial

from vultron.api.v2.backend.handlers.activity import ActivityHandler
from vultron.as_vocab.base.objects.activities.transitive import (
    as_Reject,
    as_TentativeReject,
)
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport

logger = logging.getLogger("uvicorn.error")

reject_handler = partial(ActivityHandler, activity_type=as_Reject)
tentative_reject_handler = partial(
    ActivityHandler, activity_type=as_TentativeReject
)


@tentative_reject_handler(object_type=VulnerabilityReport)
def rm_invalidate_report(
    actor_id: str,
    activity: as_TentativeReject,
) -> None:
    """
    Handle TentativeReject activity for VulnerabilityReport
    """
    obj = activity.as_object

    logger.info(
        f"Actor {actor_id} is invalidating (tentatively rejecting) a {obj.as_type}: {obj.name}"
    )


@reject_handler(object_type=VulnerabilityReport)
def rm_close_report(
    actor_id: str,
    activity: as_Reject,
) -> None:
    """
    Handle Reject activity for VulnerabilityReport
    """
    obj = activity.as_object

    logger.info(f"Actor {actor_id} is offering a {obj.as_type}: {obj.name}")
