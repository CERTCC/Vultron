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

"""Tree factory for received Announce(VulnerabilityCase) activities.

Wraps ``SeedAnnouncedCaseNode`` for use with
``BTBridge.execute_with_setup()``.
"""

import logging

import py_trees

from vultron.core.behaviors.case.nodes.announce import SeedAnnouncedCaseNode
from vultron.core.models.events.actor import (
    AnnounceVulnerabilityCaseReceivedEvent,
)
from vultron.core.models.protocols import CaseModel

logger = logging.getLogger(__name__)


def create_announce_vulnerability_case_received_tree(
    case_id: str,
    case_obj: CaseModel,
    request: AnnounceVulnerabilityCaseReceivedEvent,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for ``AnnounceVulnerabilityCaseReceivedUseCase``.

    Args:
        case_id: URI of the announced case.
        case_obj: The ``CaseModel`` instance extracted from the activity.
        request: The received event carrying the full activity context.

    Returns:
        A ``py_trees`` ``Behaviour`` ready for ``BTBridge.execute_with_setup()``.
    """
    root = SeedAnnouncedCaseNode(
        case_id=case_id,
        case_obj=case_obj,
        request=request,
    )
    logger.debug(
        "Created AnnounceVulnerabilityCaseReceivedBT for case='%s'",
        case_id,
    )
    return root
