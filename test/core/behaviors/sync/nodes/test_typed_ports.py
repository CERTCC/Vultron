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

"""Typed-Ports isolation tests for sync domain nodes (AC-4, issue #1885).

Covers BTND-03-011 (NoDataAvailable on missing required port) and happy-path
execution via BTTestScenario for sync Type-B nodes.
"""

import py_trees
import pytest
from py_trees.ports import NoDataAvailable

from vultron.core.behaviors.sync.nodes.chain import (
    PersistLogEntryNode,
    UpdateReplicationStateNode,
)
from vultron.core.behaviors.sync.nodes.fanout import (
    CollectLogEntryRecipientsNode,
    _SendLogEntryToEachNode,
)
from vultron.core.behaviors.sync.nodes.ownership_offer_effect import (
    IsOfferOwnershipTransferEventNode,
)
from vultron.core.behaviors.sync.nodes.participant_status_effect import (
    ApplyParticipantStatusFromLedgerNode,
)
from vultron.core.behaviors.sync.nodes.receive import (
    CheckHashMatchesNode,
    LogDeliveryConfirmationNode,
)
from test.core.behaviors.bt_harness import BTTestScenario

ACTOR_ID = "https://example.org/actors/vendor"


# ---------------------------------------------------------------------------
# receive.py — LogDeliveryConfirmationNode
# ---------------------------------------------------------------------------


class TestLogDeliveryConfirmationNodePorts:
    def test_missing_datalayer_raises_no_data_available(self) -> None:
        node = LogDeliveryConfirmationNode(name="LogDeliveryConfirmation")
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("datalayer")

    def test_missing_activity_raises_no_data_available(self) -> None:
        node = LogDeliveryConfirmationNode(name="LogDeliveryConfirmation")
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("activity")

    def test_failure_when_required_ports_absent(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """Ticked with no domain context, the node fails rather than hangs.

        Formerly named ``test_failure_when_datalayer_absent``, which it never
        tested: ``BTBridge.setup_tree`` always injects a datalayer, so the
        ``_require_datalayer()`` guard is unreachable from this harness. What
        actually fails the tick is the missing ``activity`` port
        (CONCERN-3019).
        """
        result = bt_scenario.run(
            LogDeliveryConfirmationNode(name="LogDeliveryConfirmation"),
            actor_id=ACTOR_ID,
        )
        bt_scenario.assert_failure(result, allow_internal=True)


# ---------------------------------------------------------------------------
# receive.py — CheckHashMatchesNode
# ---------------------------------------------------------------------------


class TestCheckHashMatchesNodePorts:
    def test_missing_datalayer_raises_no_data_available(self) -> None:
        node = CheckHashMatchesNode(name="CheckHashMatches")
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("datalayer")

    def test_missing_activity_raises_no_data_available(self) -> None:
        node = CheckHashMatchesNode(name="CheckHashMatches")
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("activity")

    def test_missing_tail_hash_raises_no_data_available(self) -> None:
        node = CheckHashMatchesNode(name="CheckHashMatches")
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("tail_hash")


# ---------------------------------------------------------------------------
# chain.py — UpdateReplicationStateNode
# ---------------------------------------------------------------------------


class TestUpdateReplicationStateNodePorts:
    def test_missing_datalayer_raises_no_data_available(self) -> None:
        node = UpdateReplicationStateNode(name="UpdateReplicationState")
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("datalayer")

    def test_missing_activity_raises_no_data_available(self) -> None:
        node = UpdateReplicationStateNode(name="UpdateReplicationState")
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("activity")


# ---------------------------------------------------------------------------
# chain.py — PersistLogEntryNode
# ---------------------------------------------------------------------------


class TestPersistLogEntryNodePorts:
    def test_missing_datalayer_raises_no_data_available(self) -> None:
        node = PersistLogEntryNode(name="PersistLogEntry")
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("datalayer")

    def test_missing_log_entry_raises_no_data_available(self) -> None:
        node = PersistLogEntryNode(name="PersistLogEntry")
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("log_entry")


# ---------------------------------------------------------------------------
# participant_status_effect.py — ApplyParticipantStatusFromLedgerNode
# ---------------------------------------------------------------------------


class TestApplyParticipantStatusFromLedgerNodePorts:
    def test_missing_datalayer_raises_no_data_available(self) -> None:
        node = ApplyParticipantStatusFromLedgerNode(
            name="ApplyParticipantStatusFromLedger"
        )
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("datalayer")

    def test_missing_activity_raises_no_data_available(self) -> None:
        node = ApplyParticipantStatusFromLedgerNode(
            name="ApplyParticipantStatusFromLedger"
        )
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("activity")


# ---------------------------------------------------------------------------
# ownership_offer_effect.py — IsOfferOwnershipTransferEventNode
# ---------------------------------------------------------------------------


class TestIsOfferOwnershipTransferEventNodePorts:
    def test_missing_datalayer_raises_no_data_available(self) -> None:
        node = IsOfferOwnershipTransferEventNode(
            name="IsOfferOwnershipTransferEvent"
        )
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("datalayer")

    def test_missing_activity_raises_no_data_available(self) -> None:
        node = IsOfferOwnershipTransferEventNode(
            name="IsOfferOwnershipTransferEvent"
        )
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("activity")


# ---------------------------------------------------------------------------
# fanout.py — _SendLogEntryToEachNode
# ---------------------------------------------------------------------------


class TestSendLogEntryToEachNodePorts:
    def test_missing_datalayer_raises_no_data_available(self) -> None:
        node = _SendLogEntryToEachNode(name="SendLogEntryToEach")
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("datalayer")

    def test_missing_log_entry_raises_no_data_available(self) -> None:
        node = _SendLogEntryToEachNode(name="SendLogEntryToEach")
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("log_entry")

    def test_missing_fanout_recipients_raises_no_data_available(self) -> None:
        node = _SendLogEntryToEachNode(name="SendLogEntryToEach")
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("fanout_recipients")


# ---------------------------------------------------------------------------
# fanout.py — CollectLogEntryRecipientsNode output port (AC-4, BTND-03-012)
# ---------------------------------------------------------------------------


class TestCollectLogEntryRecipientsNodeOutputPorts:
    def test_writes_fanout_recipients_on_success(
        self, bt_scenario: BTTestScenario
    ) -> None:
        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.models.case_ledger_entry import CaseLedgerEntry

        case_id = "https://example.org/cases/case-001"
        case = VulnerabilityCase(
            id_=case_id,
            name="Test Case",
            attributed_to=ACTOR_ID,
        )
        bt_scenario.seed(case)
        entry = CaseLedgerEntry(
            case_id=case_id,
            log_object_id="https://example.org/activities/act-001",
            event_type="close_case",
        )
        result = bt_scenario.run(
            CollectLogEntryRecipientsNode(case_id=case_id),
            actor_id=ACTOR_ID,
            log_entry=entry,
        )
        bt_scenario.assert_success(result)
        written = py_trees.blackboard.Blackboard.storage.get(
            "/fanout_recipients"
        )
        assert written is not None
        assert isinstance(written, list)
