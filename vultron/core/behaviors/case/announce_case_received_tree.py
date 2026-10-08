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

Composes ``SeedAnnouncedCaseNode`` through ``create_receive_activity_tree`` so
intake archives the Announce first (CLP-10-017).

``("Announce", "VulnerabilityCase")`` is a canonical signature, yet the tree
carries no ``case_id`` and commits nothing — a documented exemption from
CLP-10-013, not an oversight.  Only the CASE_MANAGER sends this Announce, and
the receiver trusts it only from the CASE_MANAGER it already knows (PCR-03-001,
PCR-03-004), so the receiver is a participant replica, not the manager the
commit stage is gated on (a manager's self-Announce would only duplicate the
entry it already holds).  A replica learns of case state from the ledger
fan-out (SYNC-02-002).  The commit gate here could only ever skip, and the
effect node cannot move ahead of a commit as a guard: seeding the case is
itself the write.
"""

import logging
from typing import Any

import py_trees

from vultron.core.behaviors.case.nodes.announce import SeedAnnouncedCaseNode
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.events.actor import (
    AnnounceVulnerabilityCaseReceivedEvent,
)

logger = logging.getLogger(__name__)


def create_announce_vulnerability_case_received_tree(
    case_id: str,
    case_obj: VulnerabilityCase | Any,
    request: AnnounceVulnerabilityCaseReceivedEvent,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for ``AnnounceVulnerabilityCaseReceivedUseCase``.

    Args:
        case_id: URI of the announced case.
        case_obj: The ``VulnerabilityCase`` instance extracted from the activity.
        request: The received event carrying the full activity context.

    Returns:
        The root ``Sequence``, ready for ``BTBridge.execute_with_setup()``.
    """
    root = create_receive_activity_tree(
        name="AnnounceVulnerabilityCaseReceivedBT",
        case_id=None,
        precondition_guards=[],
        replica_effects=[
            SeedAnnouncedCaseNode(
                case_id=case_id,
                case_obj=case_obj,
                request=request,
            )
        ],
    )
    logger.debug(
        "Created AnnounceVulnerabilityCaseReceivedBT for case='%s'",
        case_id,
    )
    return root
