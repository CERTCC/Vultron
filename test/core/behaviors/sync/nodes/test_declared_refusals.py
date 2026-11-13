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
tests drive each one end to end; these pin what the node itself declares.
"""

import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from test.core.behaviors.sync.nodes.conftest import CASE_ID, _make_entry
from vultron.core.behaviors.idempotency import DeclaredRefusalMixin
from vultron.core.behaviors.sync.nodes import (
    CheckEntryAgreesWithCasePositionNode,
    CheckEntryHashIntactNode,
    SendGenesisRejectOnMissingCaseNode,
    SendRejectLogEntryNode,
)
from vultron.core.behaviors.sync.nodes.ledger_position import (
    PeerActiveParticipantNode,
)
from vultron.core.behaviors.sync.nodes.position_statement import (
    CheckStatedPositionInLedgerNode,
)

_SENDER = "https://example.org/actors/sender"


@pytest.mark.parametrize(
    "node_type",
    [
        CheckEntryAgreesWithCasePositionNode,
        CheckEntryHashIntactNode,
        CheckStatedPositionInLedgerNode,
        PeerActiveParticipantNode,
        SendRejectLogEntryNode,
    ],
)
def test_each_refusing_sync_node_declares_its_refusal(node_type: type) -> None:
    assert issubclass(node_type, DeclaredRefusalMixin)


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


@pytest.mark.spec("SYNC-03-001")
def test_a_rejected_entry_is_refused_for_the_tail_it_does_not_extend() -> None:
    entry = _make_entry(log_index=3)
    assert SendRejectLogEntryNode()._refusal_of(entry) == (
        f"ledger entry '{entry.id_}' does not extend the local chain tail;"
        " Reject sent (SYNC-03-001)"
    )


@pytest.mark.spec("SYNC-15-001")
@pytest.mark.spec("SYNC-15-016")
@pytest.mark.parametrize(
    ("withheld", "spec_id"),
    [(False, "SYNC-15-001"), (True, "SYNC-15-016")],
    ids=["sent", "withheld"],
)
def test_a_missing_case_names_whether_its_genesis_reject_was_sent(
    withheld: bool, spec_id: str
) -> None:
    entry = _make_entry(log_index=0)
    node = SendGenesisRejectOnMissingCaseNode()
    node.withheld = withheld
    reason = node._refusal_of(entry)
    assert f"case '{entry.case_id}' is not seeded here" in reason
    assert reason.endswith(f"({spec_id})")
    assert ("none is sent again" in reason) is withheld
