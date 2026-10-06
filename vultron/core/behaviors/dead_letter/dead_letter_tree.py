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

"""Dead-letter BT tree factory for unresolvable-object inbox activities.

Provides a single tree factory that wraps ``StoreDeadLetterRecordNode``
into a minimal ``py_trees`` ``Behaviour`` for use with ``BTBridge``.
"""

import logging

import py_trees

from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.dead_letter.nodes import (
    StoreDeadLetterRecordNode,
)
from vultron.core.models.events.unknown import UnresolvableObjectReceivedEvent

logger = logging.getLogger(__name__)


def create_store_dead_letter_tree(
    request: UnresolvableObjectReceivedEvent,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for ``UnresolvableObjectUseCase``.

    Args:
        request: The received event carrying the unresolvable URI and
            surrounding activity context.

    Returns:
        An intake-first tree whose effect is ``StoreDeadLetterRecordNode``,
        ready for execution via
        ``BTBridge.execute_with_setup()``.
    """
    # No commit stage: a dead letter is bookkeeping, not a case assertion.
    root = create_receive_activity_tree(
        name="StoreDeadLetterBT",
        case_id=None,
        precondition_guards=[],
        effect_nodes=[StoreDeadLetterRecordNode(request=request)],
    )
    logger.debug(
        "Created StoreDeadLetterBT for activity '%s'", request.activity_id
    )
    return root
