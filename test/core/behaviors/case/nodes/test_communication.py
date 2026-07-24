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

"""
Tests for communication behavior tree nodes.

Covers SendOfferCaseManagerRoleNode and EmitRejectCaseManagerRoleNode.

Per DEMOMA-08-002, DEMOMA-08-003; Issue #469, Issue #1067.
"""

import logging
from unittest.mock import MagicMock

import py_trees
import pytest

from vultron.core.behaviors.case.nodes import (
    AutoAcceptCaseManagerRoleNode,
    CollectCaseAddresseesNode,
    CreateAndPersistCaseActivityNode,
    CreateOfferCaseManagerActivityNode,
    CreateCaseActorNode,
    EmitCreateCaseActivity,
    EmitRejectCaseManagerRoleNode,
    ResolveCaseManagerOfferContextNode,
    SendOfferCaseManagerRoleNode,
)
from vultron.core.models.vultron_types import (
    VultronCase,
    VultronCaseActor,
    VultronReport,
)
from test.core.behaviors.bt_harness import BTTestScenario

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def actor_id() -> str:
    return "https://example.org/actors/vendor"


@pytest.fixture
def actor(bt_scenario: BTTestScenario, actor_id: str) -> VultronCaseActor:
    obj = VultronCaseActor(id_=actor_id, name="Vendor Co")
    bt_scenario.dl.create(obj)
    return obj


@pytest.fixture
def report(bt_scenario: BTTestScenario) -> VultronReport:
    obj = VultronReport(name="TEST-001", content="Test vulnerability report")
    bt_scenario.dl.create(obj)
    return obj


@pytest.fixture
def case_obj(
    bt_scenario: BTTestScenario, report: VultronReport
) -> VultronCase:
    case = VultronCase(
        id_="https://example.org/cases/case-001",
        name="Test Case",
        vulnerability_reports=[report.id_],
    )
    bt_scenario.dl.create(case)
    return case


# ---------------------------------------------------------------------------
# TestEmitCreateCaseActivity
# ---------------------------------------------------------------------------


class TestEmitCreateCaseActivity:
    """EmitCreateCaseActivity composes create-case activity emission leaves."""

    def test_tree_is_sequence_with_named_leaf_nodes(self) -> None:
        tree = EmitCreateCaseActivity()
        assert isinstance(tree, py_trees.composites.Sequence)
        assert len(tree.children) == 2
        assert isinstance(tree.children[0], CollectCaseAddresseesNode)
        assert isinstance(tree.children[1], CreateAndPersistCaseActivityNode)

    def test_collect_case_addressees_filters_sender(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
        case_obj: VultronCase,
    ) -> None:
        case_obj.actor_participant_index[actor_id] = (
            "https://example.org/participants/vendor"
        )
        case_obj.actor_participant_index["https://example.org/actors/peer"] = (
            "https://example.org/participants/peer"
        )
        bt_scenario.dl.save(case_obj)

        result = bt_scenario.run(
            CollectCaseAddresseesNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )
        bt_scenario.assert_success(result)
        addressees = py_trees.blackboard.Blackboard.storage.get(
            "/create_case_addressees"
        )
        assert addressees == ["https://example.org/actors/peer"]

    def test_create_and_persist_case_activity_writes_activity_id(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
        case_obj: VultronCase,
    ) -> None:
        result = bt_scenario.run(
            CreateAndPersistCaseActivityNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
            create_case_obj=case_obj,
            create_case_addressees=[],
        )
        bt_scenario.assert_success(result)
        activity_id = py_trees.blackboard.Blackboard.storage.get(
            "/activity_id"
        )
        assert isinstance(activity_id, str)
        assert bt_scenario.dl.read(activity_id) is not None


# ---------------------------------------------------------------------------
# TestSendOfferCaseManagerRoleNode
# ---------------------------------------------------------------------------


class TestSendOfferCaseManagerRoleNode:
    """SendOfferCaseManagerRoleNode queues Offer(CaseManagerRole) to Case Actor."""

    def test_tree_is_sequence_with_named_leaf_nodes(self) -> None:
        tree = SendOfferCaseManagerRoleNode()
        assert isinstance(tree, py_trees.composites.Sequence)
        assert len(tree.children) == 2
        assert isinstance(tree.children[0], ResolveCaseManagerOfferContextNode)
        assert isinstance(tree.children[1], CreateOfferCaseManagerActivityNode)

    def test_queues_offer_and_writes_activity_id(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
        case_obj: VultronCase,
    ) -> None:
        """SendOfferCaseManagerRoleNode writes activity_id to blackboard after Offer."""
        # Run CreateCaseActorNode first to populate the DataLayer with the
        # Case Actor entity and participant.
        bt_scenario.run(
            CreateCaseActorNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )

        # Retrieve the case_actor_id that was written to the blackboard.
        case_actor_id = py_trees.blackboard.Blackboard.storage.get(
            "/case_actor_id"
        )
        assert (
            case_actor_id is not None
        ), "CreateCaseActorNode must write case_actor_id"

        case_actor_participant_id = py_trees.blackboard.Blackboard.storage.get(
            "/case_actor_participant_id"
        )
        assert (
            case_actor_participant_id is not None
        ), "CreateCaseActorNode must write case_actor_participant_id"

        # Now run SendOfferCaseManagerRoleNode with the needed blackboard context.
        result = bt_scenario.run(
            SendOfferCaseManagerRoleNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
            case_actor_id=case_actor_id,
            case_actor_participant_id=case_actor_participant_id,
        )
        bt_scenario.assert_success(result)

        activity_id = py_trees.blackboard.Blackboard.storage.get(
            "/activity_id"
        )
        assert activity_id is not None

    def test_fails_without_case_actor_id_in_blackboard(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
        case_obj: VultronCase,
    ) -> None:
        """SendOfferCaseManagerRoleNode fails if case_actor_id is not in blackboard."""
        # Provide case_id but no case_actor_id — the participant exists in DL
        # but the blackboard is missing the case_actor_id key.
        result = bt_scenario.run(
            SendOfferCaseManagerRoleNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
            # case_actor_id intentionally omitted
        )
        assert result.status == py_trees.common.Status.FAILURE


# ---------------------------------------------------------------------------
# TestEmitRejectCaseManagerRoleNode
# ---------------------------------------------------------------------------


class TestEmitRejectCaseManagerRoleNode:
    """EmitRejectCaseManagerRoleNode sends Reject(Offer(CaseManagerRole))."""

    _OFFER_ID = "https://example.org/activities/offer-cm-001"
    _CASE_ID = "https://example.org/cases/case-cm-001"
    _PARTICIPANT_ID = (
        "https://example.org/participants/urn:uuid:case-actor-cm-001"
    )
    _VENDOR_ID = "https://example.org/actors/vendor-cm"
    _CASE_ACTOR_ID = "https://example.org/actors/case-actor-cm"

    def _make_node(self) -> EmitRejectCaseManagerRoleNode:
        return EmitRejectCaseManagerRoleNode(
            offer_id=self._OFFER_ID,
            case_id=self._CASE_ID,
            participant_id=self._PARTICIPANT_ID,
            vendor_id=self._VENDOR_ID,
        )

    def _seed_dl(self, bt_scenario: BTTestScenario) -> None:
        """Seed the DataLayer with case and participant objects."""
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        case = as_VulnerabilityCase(id_=self._CASE_ID, name="CM-TEST")
        participant = as_CaseParticipant(
            id_=self._PARTICIPANT_ID,
            attributed_to=self._CASE_ACTOR_ID,
            context=self._CASE_ID,
        )
        bt_scenario.dl.create(case)
        bt_scenario.dl.create(participant)

    def test_succeeds_and_records_outbox_item(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """Returns SUCCESS and records reject activity ID in actor's outbox."""
        self._seed_dl(bt_scenario)

        result = bt_scenario.run(
            self._make_node(),
            actor_id=self._CASE_ACTOR_ID,
        )
        bt_scenario.assert_success(result)

    def test_reject_activity_persisted_to_datalayer(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """The Reject activity is stored in the DataLayer after SUCCESS."""
        self._seed_dl(bt_scenario)

        bt_scenario.run(
            self._make_node(),
            actor_id=self._CASE_ACTOR_ID,
        )

        # TriggerActivityAdapter.reject_case_manager_role persists the activity
        stored_rejects = bt_scenario.dl.list_objects("Reject")
        assert len(stored_rejects) >= 1

    def test_fails_when_trigger_factory_is_none(self) -> None:
        """Returns FAILURE when trigger_activity_factory is not available."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.behaviors.bridge import BTBridge

        dl = SqliteDataLayer("sqlite:///:memory:")
        bridge = BTBridge(
            datalayer=dl,
            is_leader=lambda: True,
            trigger_activity=None,
        )
        py_trees.blackboard.Blackboard.storage.clear()
        result = bridge.execute_with_setup(
            tree=self._make_node(),
            actor_id=self._CASE_ACTOR_ID,
        )
        assert result.status == py_trees.common.Status.FAILURE

    def test_logs_warning_when_trigger_factory_is_none(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Logs a warning at WARNING level when factory is unavailable."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.behaviors.bridge import BTBridge

        dl = SqliteDataLayer("sqlite:///:memory:")
        bridge = BTBridge(
            datalayer=dl,
            is_leader=lambda: True,
            trigger_activity=None,
        )
        py_trees.blackboard.Blackboard.storage.clear()
        with caplog.at_level(logging.WARNING):
            bridge.execute_with_setup(
                tree=self._make_node(),
                actor_id=self._CASE_ACTOR_ID,
            )
        assert any(
            "trigger_activity_factory" in r.message.lower()
            or "cannot emit reject" in r.message.lower()
            for r in caplog.records
        )

    def test_accept_or_reject_selector_in_received_tree(self) -> None:
        """AcceptOrReject Selector wraps AutoAccept + EmitReject in the tree."""
        from vultron.core.behaviors.case.offer_case_manager_role_received_tree import (
            create_offer_case_manager_role_received_tree,
        )

        tree = create_offer_case_manager_role_received_tree(
            offer_id=self._OFFER_ID,
            offer_obj=None,
            case_id=self._CASE_ID,
            participant_id=self._PARTICIPANT_ID,
            vendor_id=self._VENDOR_ID,
        )

        # The last effect node should be AcceptOrReject Selector
        # Tree structure: Sequence → [..., StoreActivityNode, AcceptOrReject]
        last_child = tree.children[-1]
        assert isinstance(last_child, py_trees.composites.Selector)
        assert last_child.name == "AcceptOrReject"
        assert len(last_child.children) == 2
        assert isinstance(
            last_child.children[0], AutoAcceptCaseManagerRoleNode
        )
        assert isinstance(
            last_child.children[1], EmitRejectCaseManagerRoleNode
        )

    def test_reject_emitted_when_accept_fails(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """When AutoAccept fails, EmitReject fires via AcceptOrReject Selector."""
        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.case.offer_case_manager_role_received_tree import (
            create_offer_case_manager_role_received_tree,
        )
        from vultron.wire.as2.factories.case import (
            offer_case_manager_role_activity,
        )
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        # Seed DL so EmitReject can reconstruct the offer
        self._seed_dl(bt_scenario)

        # Build a real offer object so StoreActivityNode can persist it
        case = as_VulnerabilityCase(id_=self._CASE_ID, name="CM-TEST")
        participant = as_CaseParticipant(
            id_=self._PARTICIPANT_ID,
            attributed_to=self._CASE_ACTOR_ID,
            context=self._CASE_ID,
        )
        offer = offer_case_manager_role_activity(
            case, target=participant, actor=self._VENDOR_ID
        )

        # Mock factory: accept raises, reject succeeds
        reject_id = "https://example.org/activities/reject-cm-001"
        mock_factory = MagicMock()
        mock_factory.accept_case_manager_role.side_effect = RuntimeError(
            "accept unavailable"
        )
        mock_factory.reject_case_manager_role.return_value = reject_id

        dl = bt_scenario.dl
        bridge = BTBridge(
            datalayer=dl,
            is_leader=lambda: True,
            trigger_activity=mock_factory,
        )

        tree = create_offer_case_manager_role_received_tree(
            offer_id=offer.id_,
            offer_obj=offer,
            case_id=self._CASE_ID,
            participant_id=self._PARTICIPANT_ID,
            vendor_id=self._VENDOR_ID,
        )
        py_trees.blackboard.Blackboard.storage.clear()
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=self._CASE_ACTOR_ID,
        )

        # EmitReject took over — Selector succeeded, Sequence succeeded
        assert result.status == py_trees.common.Status.SUCCESS
        mock_factory.reject_case_manager_role.assert_called_once_with(
            offer_id=offer.id_,
            case_id=self._CASE_ID,
            participant_id=self._PARTICIPANT_ID,
            vendor_id=self._VENDOR_ID,
            actor=self._CASE_ACTOR_ID,
            to=[self._VENDOR_ID],
        )


# ---------------------------------------------------------------------------
# TestAutoAcceptCaseManagerRoleNode
# ---------------------------------------------------------------------------


class TestAutoAcceptCaseManagerRoleNode:
    """AutoAcceptCaseManagerRoleNode commits ledger entry before enqueuing."""

    _OFFER_ID = "https://example.org/activities/offer-cm-002"
    _CASE_ID = "https://example.org/cases/case-cm-002"
    _PARTICIPANT_ID = (
        "https://example.org/participants/urn:uuid:case-actor-cm-002"
    )
    _VENDOR_ID = "https://example.org/actors/vendor-cm2"
    _CASE_ACTOR_ID = "https://example.org/actors/case-actor-cm2"

    def _make_node(self) -> AutoAcceptCaseManagerRoleNode:
        return AutoAcceptCaseManagerRoleNode(
            offer_id=self._OFFER_ID,
            case_id=self._CASE_ID,
            participant_id=self._PARTICIPANT_ID,
            vendor_id=self._VENDOR_ID,
        )

    def _seed_dl(self, bt_scenario: BTTestScenario) -> None:
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        # attributed_to triggers genesis_hash computation (CLP-08-001).
        case = as_VulnerabilityCase(
            id_=self._CASE_ID,
            name="CM-TEST-2",
            attributed_to=self._VENDOR_ID,
        )
        participant = as_CaseParticipant(
            id_=self._PARTICIPANT_ID,
            attributed_to=self._CASE_ACTOR_ID,
            context=self._CASE_ID,
        )
        bt_scenario.dl.create(case)
        bt_scenario.dl.create(participant)

    def test_succeeds_and_records_outbox_item(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """Returns SUCCESS and records accept activity ID in actor's outbox."""
        self._seed_dl(bt_scenario)

        result = bt_scenario.run(
            self._make_node(),
            actor_id=self._CASE_ACTOR_ID,
        )
        bt_scenario.assert_success(result)
        outbox = bt_scenario.dl.outbox_list_for_actor(self._CASE_ACTOR_ID)
        assert (
            len(outbox) >= 1
        ), "Expected at least one outbox item after auto-accept"

    def test_ledger_entry_created_with_correct_event_type(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """A CaseLedgerEntry with event_type 'accept_case_manager_role' is committed."""
        from vultron.core.models.case_ledger_entry import (
            VultronCaseLedgerEntry,
        )

        self._seed_dl(bt_scenario)

        bt_scenario.run(
            self._make_node(),
            actor_id=self._CASE_ACTOR_ID,
        )

        entries = bt_scenario.dl.list_objects("CaseLedgerEntry")
        accept_entries = [
            e
            for e in entries
            if isinstance(e, VultronCaseLedgerEntry)
            and e.event_type == "accept_case_manager_role"
        ]
        assert len(accept_entries) == 1, (
            "Expected exactly one 'accept_case_manager_role' ledger entry, "
            f"found {len(accept_entries)}"
        )

    def test_ledger_entry_is_recorded_not_rejected(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """The committed ledger entry has disposition 'recorded' (canonical)."""
        from vultron.core.models.case_ledger_entry import (
            VultronCaseLedgerEntry,
        )

        self._seed_dl(bt_scenario)

        bt_scenario.run(
            self._make_node(),
            actor_id=self._CASE_ACTOR_ID,
        )

        entries = bt_scenario.dl.list_objects("CaseLedgerEntry")
        accept_entries = [
            e
            for e in entries
            if isinstance(e, VultronCaseLedgerEntry)
            and e.event_type == "accept_case_manager_role"
        ]
        assert (
            accept_entries
        ), "Expected at least one 'accept_case_manager_role' ledger entry"
        assert accept_entries[0].disposition == "recorded"

    def test_accept_activity_persisted_to_datalayer(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """The Accept activity is stored in the DataLayer after SUCCESS."""
        self._seed_dl(bt_scenario)

        bt_scenario.run(
            self._make_node(),
            actor_id=self._CASE_ACTOR_ID,
        )

        stored_accepts = bt_scenario.dl.list_objects("Accept")
        assert len(stored_accepts) >= 1

    def test_fails_when_trigger_factory_is_none(self) -> None:
        """Returns FAILURE when trigger_activity_factory is not available."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.behaviors.bridge import BTBridge

        dl = SqliteDataLayer("sqlite:///:memory:")
        bridge = BTBridge(
            datalayer=dl,
            is_leader=lambda: True,
            trigger_activity=None,
        )
        py_trees.blackboard.Blackboard.storage.clear()
        result = bridge.execute_with_setup(
            tree=self._make_node(),
            actor_id=self._CASE_ACTOR_ID,
        )
        assert result.status == py_trees.common.Status.FAILURE
