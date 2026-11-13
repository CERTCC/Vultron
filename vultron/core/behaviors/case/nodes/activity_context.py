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
"""Guard: the activity's ``context`` and its object's name the same case."""

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.node_logger import node_logger


class ActivityContextMatchesObjectNode(py_trees.behaviour.Behaviour):
    """Guard: an activity and the object it carries agree on their case.

    When both the activity and its object carry a ``context`` and the two
    name different cases, the activity is refused before the commit, with a
    reason naming both: the sender has said two things about which case the
    act is for (HP-08-015).  When either names none there is nothing to
    disagree with, and the guard passes.  Both values come from the received
    message, so the guard reads nothing.

    Args:
        activity_context_id: The activity's ``context``, if any.
        object_context_id: The carried object's ``context``, if any.
        object_id: The carried object, named in the reason.
    """

    def __init__(
        self,
        activity_context_id: str | None,
        object_context_id: str | None,
        object_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.activity_context_id = activity_context_id
        self.object_context_id = object_context_id
        self.object_id = object_id

    def update(self) -> Status:
        if (
            not self.activity_context_id
            or not self.object_context_id
            or self.activity_context_id == self.object_context_id
        ):
            return Status.SUCCESS
        self.feedback_message = (
            f"the activity's context names case '{self.activity_context_id}'"
            f" but '{self.object_id}' names case '{self.object_context_id}'"
            " — REFUSED (HP-08-015)"
        )
        node_logger(self).warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


__all__ = ["ActivityContextMatchesObjectNode"]
