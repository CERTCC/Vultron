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
"""Where the embargo received trees put their factory-owned gate (BT-17-008).

The factory runs ``manager_effects`` last.  These pin what that means for
the embargo trees that had work after their gate: the Invite tree writes its
proposal index at the end of whichever arm runs, and the Add tree's
admission backfill is its gate.
"""

import py_trees
import pytest

from vultron.core.behaviors.case.nodes.role_gates import CaseManagerGate
from vultron.core.behaviors.embargo.announce_teardown_tree import (
    add_embargo_to_case_tree,
    invite_to_embargo_on_case_tree,
)
from vultron.core.behaviors.embargo.nodes import (
    IndexReceivedEmbargoProposalNode,
    SendEmbargoEndingNoticesNode,
)
from vultron.core.behaviors.sync.nodes.embargo_backfill import (
    BackfillAdmittedParticipantsNode,
)

CASE_ID = "https://example.org/cases/c1"
EMBARGO_ID = "https://example.org/embargoes/e1"
INVITE_ID = "https://example.org/activities/invite1"
ACTOR_ID = "https://example.org/actors/a1"


def _invite_tree() -> py_trees.behaviour.Behaviour:
    return invite_to_embargo_on_case_tree(
        case_id=CASE_ID,
        invitee_id=ACTOR_ID,
        invite_id=INVITE_ID,
        embargo_id=EMBARGO_ID,
        proposer_id=ACTOR_ID,
        sender_actor_id=ACTOR_ID,
    )


@pytest.mark.spec("BT-17-008")
def test_invite_tree_gate_is_last_and_ends_with_the_index() -> None:
    tree = _invite_tree()

    gate = tree.children[-1]
    assert isinstance(gate, CaseManagerGate)
    assert gate.name == "AdjudicateEmbargoProposal"
    assert isinstance(
        gate.gated_branch.children[-1], IndexReceivedEmbargoProposalNode
    )


def test_invite_tree_replica_arm_ends_with_the_index() -> None:
    tree = _invite_tree()

    (arm,) = [c for c in tree.children if c.name == "AnswerInviteOnReplica"]
    body = arm.children[-1]
    assert body.name == "AnswerInviteOnReplicaBody"
    assert isinstance(body.children[-1], IndexReceivedEmbargoProposalNode)


def test_invite_tree_indexes_once_per_arm() -> None:
    indexes = [
        n
        for n in _invite_tree().iterate()
        if isinstance(n, IndexReceivedEmbargoProposalNode)
    ]

    assert len(indexes) == 2


@pytest.mark.spec("BT-17-008")
def test_add_embargo_backfill_is_the_factory_gate() -> None:
    tree = add_embargo_to_case_tree(
        case_id=CASE_ID, embargo_id=EMBARGO_ID, sender_actor_id=ACTOR_ID
    )

    gate = tree.children[-1]
    assert isinstance(gate, CaseManagerGate)
    assert gate.name == "EmbargoAdmissionBackfill"
    # The CM-31-009 notices, then the CM-10-006 backfill, both gated.
    children = gate.gated_branch.children
    assert [type(c) for c in children] == [
        SendEmbargoEndingNoticesNode,
        BackfillAdmittedParticipantsNode,
    ]
