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

"""The end-time and termination-cascade nodes read their per-act values from
act keys (BTND-01-008, #6505).

Each node takes only configuration in its constructor.  A node ticked with no
seed for a key it requires is a composition fault: the read raises, naming
the key, rather than the node deciding anything without it.
"""

from collections.abc import Callable

import py_trees
import pytest
from py_trees.ports import NoDataAvailable

from test.core.behaviors.embargo.nodes.conftest import setup_blackboard
from test.support.act_runner import in_act
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.case.nodes.leave.settle import (
    ExpirePendingInvitesOnCloseNode,
)
from vultron.core.behaviors.embargo.end_time_tree import (
    EmbargoAlreadyEndedNode,
    EmbargoEndTimePassedNode,
)
from vultron.core.behaviors.embargo.nodes.cascade import (
    PersistEmbargoEventNode,
)
from vultron.core.behaviors.embargo.nodes.chosen_cause import (
    ChooseTerminationCauseNode,
    ChosenTermination,
)
from vultron.core.behaviors.embargo.nodes.ending_notice import (
    CaptureActiveEmbargoNode,
    SendEmbargoEndingNoticesNode,
)
from vultron.core.behaviors.embargo.nodes.ending_notice_replica import (
    AdoptRemovedEmbargoRevisionNode,
    ApplyAnnouncedEmbargoRevisionNode,
    AwaitsEmbargoEndingNoticeNode,
)
from vultron.core.behaviors.embargo.nodes.expiry import (
    EvaluateInviteExpiryNode,
)
from vultron.core.behaviors.embargo.nodes.expiry_commit import (
    CommitAndApplyInviteExpiryNode,
)
from vultron.core.behaviors.embargo.nodes.invitation_expiry import (
    ExpireOverdueInvitesNode,
)
from vultron.core.behaviors.embargo.nodes.teardown import (
    ClearActiveEmbargoNode,
    HasEmbargoActiveNode,
    SendAnnounceEmbargoEventNode,
    TerminationIsTimelyNode,
)
from vultron.core.behaviors.embargo.nodes.terminate import (
    SendTerminateEmbargoActivityNode,
    TeardownAskPendingNode,
)
from vultron.core.behaviors.embargo.nodes.termination_cause_guard import (
    TerminationCauseIsAdmissibleNode,
)
from vultron.core.behaviors.embargo.nodes.termination_commit import (
    CommitAndApplyEmbargoTerminationNode,
)
from vultron.core.models.embargo_termination import (
    EmbargoTermination,
    TerminationCauseKind,
)
from vultron.core.states.embargo_register import TerminationReason

#: Each moved node, built from configuration alone, and the first key it
#: reads when it ticks.
_NODES: list[tuple[Callable[[], py_trees.behaviour.Behaviour], str]] = [
    (lambda: EmbargoAlreadyEndedNode(result_out={}), "/case_id"),
    (EmbargoEndTimePassedNode, "/case_id"),
    (PersistEmbargoEventNode, "/embargo"),
    (
        lambda: ChooseTerminationCauseNode(
            kind=TerminationCauseKind.OTHER, chosen=ChosenTermination()
        ),
        "/case_id",
    ),
    (CaptureActiveEmbargoNode, "/case_id"),
    (
        lambda: SendEmbargoEndingNoticesNode(
            capture=CaptureActiveEmbargoNode()
        ),
        "/case_id",
    ),
    (AwaitsEmbargoEndingNoticeNode, "/case_id"),
    (ApplyAnnouncedEmbargoRevisionNode, "/case_id"),
    (AdoptRemovedEmbargoRevisionNode, "/case_id"),
    (lambda: EvaluateInviteExpiryNode(result_out={}), "/case_id"),
    (CommitAndApplyInviteExpiryNode, "/case_id"),
    (ExpireOverdueInvitesNode, "/case_id"),
    (ExpirePendingInvitesOnCloseNode, "/case_id"),
    (
        lambda: ClearActiveEmbargoNode(termination=EmbargoTermination.early()),
        "/case_id",
    ),
    (HasEmbargoActiveNode, "/case_id"),
    (SendAnnounceEmbargoEventNode, "/case_id"),
    (
        lambda: TerminationIsTimelyNode(
            termination=EmbargoTermination.early()
        ),
        "/case_id",
    ),
    (
        lambda: SendTerminateEmbargoActivityNode(
            reason=TerminationReason.EARLY
        ),
        "/case_id",
    ),
    (TeardownAskPendingNode, "/case_id"),
    (
        lambda: TerminationCauseIsAdmissibleNode(
            termination=EmbargoTermination.early()
        ),
        "/case_id",
    ),
    (
        lambda: CommitAndApplyEmbargoTerminationNode(
            result_out={}, termination=EmbargoTermination.early()
        ),
        "/case_id",
    ),
]


@pytest.mark.spec("BTND-01-008")
@pytest.mark.parametrize(
    ("build", "key"),
    _NODES,
    ids=[f"{i:02d}" for i in range(len(_NODES))],
)
def test_a_node_ticked_without_its_key_seeded_raises_naming_the_key(
    build: Callable[[], py_trees.behaviour.Behaviour], key: str
) -> None:
    py_trees.blackboard.Blackboard.storage.pop(key, None)
    setup_blackboard(
        SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://example.org/users/vendor",
        )
    )
    tree = py_trees.trees.BehaviourTree(root=build())
    tree.setup()

    with in_act(), pytest.raises(NoDataAvailable, match=key):
        tree.tick()
