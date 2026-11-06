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
        A doors-then-intake tree whose effect is ``StoreDeadLetterRecordNode``,
        ready for execution via
        ``BTBridge.execute_with_setup()``.
    """
    # No commit stage: a dead letter is bookkeeping, not a case assertion.
    #
    # And no path declaration (HP-01-038).  The tree is not a message type's:
    # it runs for any activity whose ``object_`` URI did not resolve, so there
    # is no type whose paths it could declare.  What it does is the receiver's
    # own diagnostic — a ``DeadLetterRecord`` that names no case — and no
    # branch of this tree is keyed on the path, so a path stage would read
    # the receiver's role (HP-01-037) in a case the activity only happens to
    # mention and nothing would use the answer (HP-01-038).  The factory's
    # shared post-close door does still ask that role for itself, ahead of
    # the stage and for its own reason (CM-23-013); it is not a branch of
    # this tree.  The reason is pinned beside the intake-only trees' in
    # ``UNDECLARED_PATH_EXEMPTIONS``
    # (``test/core/behaviors/test_declared_received_paths.py``).
    root = create_receive_activity_tree(
        name="StoreDeadLetterBT",
        case_id=None,
        precondition_guards=[],
        replica_effects=[StoreDeadLetterRecordNode(request=request)],
    )
    logger.debug(
        "Created StoreDeadLetterBT for activity '%s'", request.activity_id
    )
    return root
