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
"""Structure of the owner-Leave arm of the close-case tree (ADR-0152).

The owner arm records the Case Owner's closure, settles every pending
embargo Invite, then records the CASE_MANAGER's own closure last: its
``RM.CLOSED`` status entry is the write boundary (CM-23-002, CM-23-013,
CM-23-014).  No node commits a separate closure marker.
"""

from __future__ import annotations

import py_trees
import pytest

from vultron.core.behaviors.case.receive_close_case_tree import (
    create_close_case_received_tree,
)
from vultron.core.use_cases.received.case.lifecycle import (
    CloseCaseReceivedUseCase,
)
from vultron.errors import VultronWiringError

CASE_ID = "https://example.org/cases/c-close-tree"
OWNER_ID = "https://example.org/actors/owner-close-tree"


def _find(
    root: py_trees.behaviour.Behaviour, name: str
) -> py_trees.behaviour.Behaviour:
    for node in root.iterate():
        if node.name == name:
            return node
    raise AssertionError(f"no node named {name!r} in the tree")


def _owner_tree() -> py_trees.behaviour.Behaviour:
    return create_close_case_received_tree(
        case_id=CASE_ID,
        activity_id="https://example.org/activities/leave-1",
        sender_actor_id=OWNER_ID,
        receiving_actor_id="https://example.org/actors/case-actor",
        sender_rule=CloseCaseReceivedUseCase.sender_entitlement,
    )


@pytest.mark.spec("CM-23-002")
@pytest.mark.spec("CM-23-014")
def test_the_owner_arm_closes_the_case_manager_last():
    owner_arm = _find(_owner_tree(), "OwnerLeaveSeq")

    # Settling first keeps every closure entry, the boundary included,
    # after the expiries, even when the Case Owner is the CASE_MANAGER.
    assert [child.name for child in owner_arm.children] == [
        "ExpirePendingInvitesOnClose",
        "AdvanceOwnerToRMClosed",
        "CommitOwnerRMClosureEntries",
        "AdvanceCaseActorToRMClosed",
        "CommitCaseActorRMClosureEntries",
    ]


@pytest.mark.spec("CM-23-002")
def test_no_node_commits_a_closure_marker():
    names = {node.name for node in _owner_tree().iterate()}

    assert not {n for n in names if "FullyClosed" in n}


@pytest.mark.spec("HP-01-008")
def test_a_leave_with_a_sender_and_no_sender_rule_is_a_wiring_error():
    """The factory composes the sender guard from the declared rule; a tree
    built without one would run the closure for any sender."""
    with pytest.raises(VultronWiringError, match="HP-01-008"):
        create_close_case_received_tree(
            case_id=CASE_ID,
            activity_id="https://example.org/activities/leave-1",
            sender_actor_id=OWNER_ID,
            receiving_actor_id="https://example.org/actors/case-actor",
        )
