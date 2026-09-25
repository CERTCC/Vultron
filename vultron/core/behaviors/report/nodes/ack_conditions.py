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
"""Condition nodes for the received-side AckReport tree.

- :class:`CheckSenderIsExecutingActorNode` — the ``Read(Offer(Report))`` was
  sent by the actor executing the tree, i.e. it is that actor's *own*
  acknowledgement arriving in its own inbox.

References
----------
- Issue: #2667 (ack echo from actors that did not send the ack)
"""

import logging

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.predicates.addressing import same_actor_id

logger = logging.getLogger(__name__)


class CheckSenderIsExecutingActorNode(DataLayerConditionWithPorts):
    """SUCCESS when *sender_actor_id* is the executing actor.

    Comparison uses :func:`~vultron.core.predicates.addressing.same_actor_id`,
    so the two ids may differ by a trailing slash.
    """

    def __init__(self, sender_actor_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.sender_actor_id = sender_actor_id

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.actor_id is not None

        if same_actor_id(self.sender_actor_id, self.actor_id):
            return Status.SUCCESS
        self.logger.debug(
            "%s: sender '%s' is not the executing actor '%s'",
            self.name,
            self.sender_actor_id,
            self.actor_id,
        )
        return Status.FAILURE
