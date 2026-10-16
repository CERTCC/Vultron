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

"""The guard that turns away a received activity its tree cannot judge.

A received handler's tree needs some values from the activity before it can
be built at all: the case it names, the participant a move names, the
proposal's id.  An activity that lacks one cannot reach its guards, commit or
effects, yet it still arrived, so the receiver keeps it (CLP-10-018) and
refuses it inside the one tree it runs for the delivery (CLP-10-005,
ADR-0135).

:class:`ActivityIncompleteNode` is that refusal.  A tree factory that finds
the activity incomplete composes it as the tree's only precondition guard,
through
:func:`~vultron.core.behaviors.case.intake_only_received_tree.create_incomplete_activity_received_tree`,
so intake archives the activity first and nothing else runs.
"""

import logging

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.node_logger import node_logger

__all__ = ["ActivityIncompleteNode"]


class ActivityIncompleteNode(py_trees.behaviour.Behaviour):
    """Guard: refuse a received activity that lacks what its tree needs.

    Always ``FAILURE``, with *reason* as the feedback message, which names
    what the activity is missing.  It reads and writes nothing: the factory
    that composes it has already found the activity incomplete.
    """

    logger: logging.Logger  # type: ignore[assignment]

    def __init__(self, reason: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.reason = reason
        self.logger = node_logger(self)  # type: ignore[assignment]

    def update(self) -> Status:
        self.feedback_message = self.reason
        self.logger.warning("%s: %s — refusing", self.name, self.reason)
        return Status.FAILURE
