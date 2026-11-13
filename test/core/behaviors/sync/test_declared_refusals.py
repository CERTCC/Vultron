#!/usr/bin/env python
#
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
"""The SYNC nodes that declare their failure a refusal of the activity (#5775).

Each names its condition and the requirement it cites, which the received
runner reports as the ``REFUSED`` reason
(:class:`~vultron.core.behaviors.idempotency.ReportsRefusal`).  The handler
tests drive each one end to end and pin its whole reason; these pin the
branches a handler test does not reach.
"""

import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from vultron.core.behaviors.sync.nodes import SendRejectLogEntryNode
from vultron.core.behaviors.sync.nodes.ledger_position import (
    PeerActiveParticipantNode,
)
from vultron.errors import VultronWiringError

CASE_ID = "https://example.org/cases/declared-refusal"
_SENDER = "https://example.org/actors/sender"


@pytest.mark.spec("SYNC-17-002")
def test_an_undecided_standing_asked_for_active_is_a_refusal(
    bt_scenario: BTTestScenario,
) -> None:
    """A case this store does not hold leaves the standing undecided."""
    node = PeerActiveParticipantNode(
        case_id=CASE_ID, sender_id=_SENDER, active=True
    )
    bt_scenario.run(node)
    assert node.status == Status.FAILURE
    assert node.declared_refusal is not None
    assert node.declared_refusal.startswith(node.feedback_message)
    assert node.declared_refusal.endswith(
        "; no replication state recorded and no entry replayed (SYNC-17-002)"
    )


def test_the_branch_asked_for_not_active_declares_no_refusal(
    bt_scenario: BTTestScenario,
) -> None:
    """``active=False`` only picks a branch of the position answer."""
    node = PeerActiveParticipantNode(
        case_id=CASE_ID, sender_id=_SENDER, active=False
    )
    bt_scenario.run(node)
    assert node.status == Status.FAILURE
    assert node.declared_refusal is None


def test_a_reject_node_with_no_actor_raises_rather_than_refusing() -> None:
    """A Reject with no sender identity is our fault (ADR-0095)."""
    node = SendRejectLogEntryNode()
    node.actor_id = None
    node.activity = object()
    with pytest.raises(VultronWiringError, match="actor_id"):
        node.update()
    assert node.declared_refusal is None
