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

Also covers the ``log_entry`` / ``replay_entry`` ledger-handoff type contract
(#2907): both keys carry a ``VultronCaseLedgerEntry`` and every declaration
says so, so a wrong-typed value is rejected at the port instead of reaching the
``cast(VultronCaseLedgerEntry, ...)`` in each node's ``update()``.
"""

from typing import Any

import py_trees
import pytest
from py_trees.ports import NoDataAvailable

import vultron.core.behaviors.sync.nodes as sync_nodes_pkg
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
from vultron.core.models.case_ledger_entry import VultronCaseLedgerEntry
from test.core.behaviors.bt_harness import BTTestScenario
from test.core.behaviors.port_contract import (
    PortDecl,
    decl_id,
    discover_port_declarations,
)

ACTOR_ID = "https://example.org/actors/vendor"
LEDGER_CASE_ID = "https://example.org/cases/case-ledger"

#: The two ledger-entry handoff keys, with the physical blackboard key each
#: logical port is remapped to (both are static, not execution-scoped).
LEDGER_PORTS: dict[str, str] = {
    "log_entry": "/log_entry",
    "replay_entry": "/replay_entry",
}

#: Constructor kwargs for every node in the discovered ledger-port roster.  A
#: new node must be registered here; the coverage test below fails otherwise,
#: so it cannot be silently dropped from the enforcement tests.
LEDGER_NODE_KWARGS: dict[str, dict[str, Any]] = {
    "CollectAndSortCaseLedgerEntriesNode": {
        "name": "CollectAndSortCaseLedgerEntries"
    },
    "CollectLogEntryRecipientsNode": {"case_id": LEDGER_CASE_ID},
    "CollectNonClosedLogEntryRecipientsNode": {"case_id": LEDGER_CASE_ID},
    "CreateLogEntryNode": {
        "case_id": LEDGER_CASE_ID,
        "object_id": "https://example.org/activities/act-001",
        "event_type": "close_case",
    },
    "PersistLogEntryNode": {"name": "PersistLogEntry"},
    "SendLogEntryToEachNode": {},
    "SendMissingEntriesNode": {},
    "_SendLogEntryToEachNode": {},
}

#: Extra blackboard context a node needs before its ``initialise()`` reaches
#: the ledger port.  ``SendMissingEntriesNode`` reads ``case_actor_id`` first,
#: so without it the tick fails on that port instead of the one under test.
LEDGER_TICK_EXTRAS: dict[str, dict[str, Any]] = {
    "SendMissingEntriesNode": {
        "case_actor_id": "https://example.org/actors/case-actor"
    },
}


LEDGER_READERS, LEDGER_WRITERS = discover_port_declarations(
    sync_nodes_pkg, LEDGER_PORTS
)


def _build_ledger_node(node_cls: type) -> Any:
    return node_cls(**LEDGER_NODE_KWARGS[node_cls.__name__])


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

    def test_failure_when_datalayer_absent(
        self, bt_scenario: BTTestScenario
    ) -> None:
        result = bt_scenario.run(
            LogDeliveryConfirmationNode(name="LogDeliveryConfirmation"),
            actor_id=ACTOR_ID,
        )
        bt_scenario.assert_failure(result)


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


# ---------------------------------------------------------------------------
# Ledger-entry handoff type contract (#2907)
# ---------------------------------------------------------------------------


def _make_ledger_entry() -> VultronCaseLedgerEntry:
    return VultronCaseLedgerEntry(
        case_id=LEDGER_CASE_ID,
        log_object_id="https://example.org/activities/act-001",
        event_type="close_case",
    )


class TestLedgerPortRosterDiscovery:
    @pytest.mark.parametrize("port", sorted(LEDGER_PORTS))
    def test_port_has_a_reader_and_a_writer(self, port: str) -> None:
        """Guard against a refactor that silently empties the parametrize."""
        assert any(
            p == port for _, p in LEDGER_READERS
        ), f"no {port} readers discovered"
        assert any(
            p == port for _, p in LEDGER_WRITERS
        ), f"no {port} writers discovered"

    def test_constructor_table_matches_the_discovered_roster(self) -> None:
        """The table and the roster stay in step in both directions.

        Missing entries would drop a node from the enforcement tests; stale
        ones would outlive the node they name and never be noticed.
        """
        discovered = {
            cls.__name__ for cls, _ in LEDGER_READERS + LEDGER_WRITERS
        }
        assert discovered == set(LEDGER_NODE_KWARGS)

    def test_tick_extras_name_only_discovered_nodes(self) -> None:
        """A stale ``LEDGER_TICK_EXTRAS`` key would mask nothing but confuse."""
        discovered = {cls.__name__ for cls, _ in LEDGER_READERS}
        assert set(LEDGER_TICK_EXTRAS) <= discovered


@pytest.mark.spec("BTND-03-009")
class TestLedgerPortDeclarations:
    """Every tracked declaration names the ledger-entry class.

    ``VultronCaseLedgerEntry`` is an alias of ``CaseLedgerEntry`` (the same
    class object), so these assertions check that the declaration is the ledger
    entry type at all — they do not distinguish the two names, and would pass
    equally for ``data_type=CaseLedgerEntry``. What the tightening excludes is a
    value that is not a ``CaseLedgerEntry``.
    """

    @pytest.mark.parametrize("decl", LEDGER_READERS, ids=decl_id)
    def test_reader_declares_ledger_entry(self, decl: PortDecl) -> None:
        node_cls, port_name = decl
        port = node_cls.input_ports()[port_name]  # type: ignore[attr-defined]
        assert port.data_type is VultronCaseLedgerEntry
        assert port.required is True

    @pytest.mark.parametrize("decl", LEDGER_WRITERS, ids=decl_id)
    def test_writer_declares_ledger_entry(self, decl: PortDecl) -> None:
        node_cls, port_name = decl
        port = node_cls.output_ports()[port_name]  # type: ignore[attr-defined]
        assert port.data_type is VultronCaseLedgerEntry
        assert port.required is True


@pytest.mark.spec("BTND-03-011")
class TestLedgerPortInputEnforcement:
    # py_trees' blackboard storage is a process-global singleton; the repo-wide
    # autouse `clear_py_trees_blackboard` in test/core/behaviors/conftest.py
    # clears it around every test in this tree (TB-06-005).

    @pytest.mark.parametrize("decl", LEDGER_READERS, ids=decl_id)
    def test_wrong_type_raises_type_error(self, decl: PortDecl) -> None:
        node_cls, port = decl
        node = _build_ledger_node(node_cls)
        node.setup()
        py_trees.blackboard.Blackboard.set(LEDGER_PORTS[port], "not-an-entry")
        with pytest.raises(TypeError, match="not of type"):
            node.get_input(port)

    @pytest.mark.parametrize("decl", LEDGER_READERS, ids=decl_id)
    def test_ledger_entry_is_accepted(self, decl: PortDecl) -> None:
        node_cls, port = decl
        node = _build_ledger_node(node_cls)
        node.setup()
        entry = _make_ledger_entry()
        py_trees.blackboard.Blackboard.set(LEDGER_PORTS[port], entry)
        assert node.get_input(port) is entry


@pytest.mark.spec("BTND-03-012")
class TestLedgerPortOutputEnforcement:
    @pytest.mark.parametrize("decl", LEDGER_WRITERS, ids=decl_id)
    def test_writer_rejects_wrong_type(self, decl: PortDecl) -> None:
        node_cls, port = decl
        node = _build_ledger_node(node_cls)
        node.setup()
        with pytest.raises(TypeError, match="not of type"):
            node._set_output(port, "not-an-entry")

    @pytest.mark.parametrize("decl", LEDGER_WRITERS, ids=decl_id)
    def test_writer_accepts_ledger_entry(self, decl: PortDecl) -> None:
        node_cls, port = decl
        node = _build_ledger_node(node_cls)
        node.setup()
        entry = _make_ledger_entry()
        node._set_output(port, entry)
        assert py_trees.blackboard.Blackboard.get(LEDGER_PORTS[port]) is entry


@pytest.mark.spec("BTND-03-011")
class TestLedgerPortTickLevelEnforcement:
    """The type check is reached on the real production read path.

    Every ledger-port reader calls ``get_input()`` directly in
    ``initialise()``, so the ``TypeError`` propagates out of the tick and
    ``BTBridge.execute_tree`` converts it into a tree-level FAILURE carrying
    the type-mismatch message. Asserting on that message (not merely on
    FAILURE) is what distinguishes a rejected value from a node that quietly
    treated the junk as absent.
    """

    @pytest.mark.parametrize("decl", LEDGER_READERS, ids=decl_id)
    def test_junk_on_key_fails_tree_with_type_error(
        self, bt_scenario: BTTestScenario, decl: PortDecl
    ) -> None:
        node_cls, port = decl
        result = bt_scenario.run(
            _build_ledger_node(node_cls),
            actor_id=ACTOR_ID,
            **{port: "not-an-entry"},
            **LEDGER_TICK_EXTRAS.get(node_cls.__name__, {}),
        )
        bt_scenario.assert_failure(result)
        errors = result.errors or []
        assert any(
            "not of type" in err for err in errors
        ), f"expected a port type-mismatch error, got {errors}"
