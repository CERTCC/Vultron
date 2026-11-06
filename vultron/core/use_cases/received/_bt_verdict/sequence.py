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

"""The verdict owed when the sender sequence stage stopped the tree (SYNC-21).

The factory places the stage after the door guards in every case tree
(``sender_sequence_stage``).  When it does not let the activity be judged
now, the run ends there, and the handler reports what the stage decided
rather than a refusal of the act's merits.
"""

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.sync.nodes.sender_sequence import (
    SequenceAdmitsNode,
)
from vultron.core.models.use_case_result import HandlerResult
from vultron.core.services.sender_sequence_order import SequenceStanding
from vultron.core.use_cases.received._bt_verdict.tree_lookup import (
    _HasRoot,
    find_node,
)


def sender_sequence_verdict(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
) -> HandlerResult | None:
    """The verdict of a run the sender sequence stage ended, else ``None``.

    - An activity held past a gap is ``DEFERRED``: it is judged later, as a
      delivery of its own (SYNC-21-010).
    - A repeat of a held activity is ``SKIPPED``: the held copy stays
      (SYNC-21-018).
    - A late, reused or missing number, and a repeat of an activity refused
      for its number, are ``REFUSED`` with the stage's reason (SYNC-21-014,
      SYNC-21-017).
    """
    node = find_node(tree, SequenceAdmitsNode)
    if node is None or node.status != Status.FAILURE:
        return None
    reason = node.feedback_message or node.classify.refusal_reason()
    standing = node.classify.standing
    if standing is SequenceStanding.AHEAD:
        return HandlerResult.deferred(reason)
    if standing is SequenceStanding.HELD_REPEAT:
        return HandlerResult.skipped(reason)
    return HandlerResult.refused(reason)


__all__ = ["sender_sequence_verdict"]
