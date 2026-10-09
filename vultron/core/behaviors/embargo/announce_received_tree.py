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

"""Received ``Announce(EmbargoEvent)``: a paused replica's shorter revision.

An ``Announce(EmbargoEvent)`` is canonical case state only the CASE_MANAGER
asserts; the use case refuses any other sender before this tree runs
(ADR-0115, PCR-03-001).  An active replica takes every embargo change from
the ledger (RSH-08-003), so for it the tree only archives the activity.  A
signatory of the embargo in force whose ledger stream is paused — removed,
or at RM ``CLOSED`` — cannot, and the announcement is the CM-31-009 notice
of a shorter revision: it applies it through ``EmbargoLifecycle``
(CM-31-010).  A withheld replica (CM-10-005) is bound by no embargo in
force, so no notice is owed to it; what reaches it is the teardown
announcement, and it only archives that too::

    AnnounceEmbargoEventToCaseReceivedBT (Sequence)
    ├─ IntakeReceivedActivityNode
    └─ ApplyIfEndingNoticeAwaited (Selector)
       ├─ SkipUnlessEndingNoticeAwaited (Inverter)
       │  └─ AwaitsEmbargoEndingNoticeNode
       └─ ApplyAnnouncedEmbargoRevisionNode

No ledger entry is committed: the announcement is a notice, not a record.
"""

import py_trees

from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.embargo.nodes import (
    ApplyAnnouncedEmbargoRevisionNode,
    AwaitsEmbargoEndingNoticeNode,
)
from vultron.core.models.embargo_event import EmbargoEvent


def announce_embargo_received_tree(
    case_id: str,
    embargo_id: str,
    embargo: EmbargoEvent | None = None,
) -> py_trees.composites.Sequence:
    """Build the received ``Announce(EmbargoEvent)`` tree (CM-31-010).

    Args:
        case_id: The case the announcement is for (its ``context``).
        embargo_id: The announced ``EmbargoEvent``.
        embargo: The announced embargo when carried inline; stored by the
            apply node before activation when the replica lacks it.
    """
    return create_receive_activity_tree(
        name="AnnounceEmbargoEventToCaseReceivedBT",
        case_id=None,
        precondition_guards=[],
        replica_effects=[
            py_trees.composites.Selector(
                name="ApplyIfEndingNoticeAwaited",
                memory=False,
                children=[
                    py_trees.decorators.Inverter(
                        name="SkipUnlessEndingNoticeAwaited",
                        child=AwaitsEmbargoEndingNoticeNode(case_id=case_id),
                    ),
                    ApplyAnnouncedEmbargoRevisionNode(
                        case_id=case_id,
                        embargo_id=embargo_id,
                        embargo=embargo,
                    ),
                ],
            ),
        ],
    )


__all__ = ["announce_embargo_received_tree"]
