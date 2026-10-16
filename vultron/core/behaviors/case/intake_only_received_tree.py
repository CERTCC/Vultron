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

"""Shared intake-only tree for received handlers that commit nothing (#3871).

Every intake-only received handler builds this one tree and runs it once
(CLP-10-005): intake archives the activity it received (CLP-10-017,
CLP-10-018), and nothing else runs.  There are no guards, no commit and no
effects, so the tree writes nothing to the case file.

Why no commit (``case_id=None``): a handler uses this tree only for an
activity that records no case event on a CLP-02-013 ground (a
``Create(ProcessingFault)`` NACK, an activity only the CASE_MANAGER sends,
received by a participant).  The commit-coverage gate
(``test/architecture/test_ledger_commit_coverage.py``) names each user's
ground, or the open issue tracking its missing entry.

The tree never stores the object a ``Create(X)`` introduces.  A ``Create`` of a
case record is a change to the case file, and a change with no committed entry
MUST NOT be made (CLP-07-013), so a handler that stores one needs a commit and
cannot use this tree.

:func:`create_incomplete_activity_received_tree` is the same tree with one
guard, :class:`~vultron.core.behaviors.case.nodes.incomplete_activity.ActivityIncompleteNode`:
a handler's tree factory returns it for an activity that lacks a value the
handler's own tree needs to be built, so the refusal is a guard in the one
tree the delivery runs (CLP-10-005, ADR-0135) and the activity is still
archived (CLP-10-018).
"""

import py_trees

from vultron.core.behaviors.case.nodes.incomplete_activity import (
    ActivityIncompleteNode,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)


def create_intake_only_received_tree(
    name: str,
) -> py_trees.composites.Sequence:
    """Build the intake-only tree.

    Args:
        name: Name for the root ``Sequence``.
    """
    return create_receive_activity_tree(
        name=name,
        case_id=None,
        precondition_guards=[],
        replica_effects=[],
    )


def create_incomplete_activity_received_tree(
    name: str,
    reason: str,
) -> py_trees.composites.Sequence:
    """Build the tree that archives an incomplete activity and refuses it.

    Intake → post-close guard → ``ActivityIncompleteNode``: nothing is
    committed and no effect runs, and the handler reads the guard's
    ``FAILURE`` as ``REFUSED`` for *reason*.

    Args:
        name: Name for the root ``Sequence``; the handler's own tree name.
        reason: What the activity is missing, as the refusal states it.
    """
    return create_receive_activity_tree(
        name=name,
        case_id=None,
        precondition_guards=[ActivityIncompleteNode(reason)],
        replica_effects=[],
    )
