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

"""Trigger-side behavior tree for add-object-to-case workflows."""

from collections.abc import Callable

import py_trees

from vultron.core.behaviors.sender.send_tree import sender_side_bt


def add_object_trigger_bt(
    case_id: str,
    activity_builder: Callable[[str], list[str]],
) -> py_trees.behaviour.Behaviour:
    """Return the trigger-side BT for ``Add(object, target=Case)``.

    Routes the ``Add`` to the CASE_MANAGER alone through
    :func:`~vultron.core.behaviors.sender.send_tree.sender_side_bt`
    (PCR-08-001, PCR-08-005).  The tree fails before anything is built or
    queued when the case has no CASE_MANAGER.

    Args:
        case_id: ID of the VulnerabilityCase.
        activity_builder: Closure called with the resolved CASE_MANAGER ID;
            returns the list of outbound activity IDs.

    Returns:
        SenderSideBT Sequence.
    """
    return sender_side_bt(case_id=case_id, activity_builder=activity_builder)
