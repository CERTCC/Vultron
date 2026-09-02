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
Tests for case_setup behavior tree nodes.

Covers:
- UpdateActorOutbox re-export via case.nodes and report.nodes (P360-FIX-1)
- RecordCaseCreationEvents blackboard key contract (P360-FIX-3)
- CreateCaseActorNode blackboard variant
- ResolveCaseActorUrlsNode: reads case_actor_service_url from ActorConfig (CP-08-002)

Per specs/behavior-tree-node-design.yaml BTND-02-001, BTND-03-001, BTND-04-001
and GitHub issue #401.
"""

from unittest.mock import MagicMock

import py_trees
import pytest

from vultron.core.behaviors.case.nodes import (
    RecordCaseCreatedEventNode,
    RecordCaseCreationEvents,
    RecordOfferReceivedEventNode,
    UpdateActorOutbox,
)
from vultron.core.behaviors.helpers import (
    UpdateActorOutbox as UpdateActorOutboxHelper,
)
from vultron.core.behaviors.report.nodes import (
    UpdateActorOutbox as UpdateActorOutboxReport,
)
from vultron.core.models.vultron_types import (
    VultronCase,
    VultronCaseActor,
    VultronReport,
)
from test.core.behaviors.bt_harness import BTTestScenario

# The URL used by tests as the CaseActor service base URL (CP-08-001).
_CASE_ACTOR_SERVICE_URL = "http://case-actor:7999/api/v2"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def configure_case_actor_url(monkeypatch):
    """Set VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL for tests that exercise
    ResolveCaseActorUrlsNode so the node finds a configured URL."""
    monkeypatch.setenv(
        "VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL", _CASE_ACTOR_SERVICE_URL
    )
    from vultron.config.app import reload_config

    reload_config()
    yield
    # Undo the env patch BEFORE reloading: monkeypatch's own undo runs after
    # this teardown, so reloading first would re-cache this fixture's URL into
    # the module-level config for the rest of the session (#2086).
    monkeypatch.undo()
    reload_config()


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
# P360-FIX-1: UpdateActorOutbox re-export tests
# ---------------------------------------------------------------------------


class TestUpdateActorOutboxReExport:
    """UpdateActorOutbox is the same object in all three modules (BTND-04-001)."""

    def test_case_nodes_re_exports_from_helpers(self) -> None:
        assert UpdateActorOutbox is UpdateActorOutboxHelper

    def test_report_nodes_re_exports_from_helpers(self) -> None:
        assert UpdateActorOutboxReport is UpdateActorOutboxHelper

    def test_shared_class_is_not_duplicate(self) -> None:
        """There is exactly one UpdateActorOutbox class definition."""
        assert (
            UpdateActorOutbox
            is UpdateActorOutboxReport
            is UpdateActorOutboxHelper
        )


# ---------------------------------------------------------------------------
# P360-FIX-3: RecordCaseCreationEvents blackboard key contract
# ---------------------------------------------------------------------------


class TestRecordCaseCreationEvents:
    """Blackboard keys are declared; activity key is optional (BTND-03-001/02)."""

    def test_tree_is_sequence_with_named_leaf_nodes(self) -> None:
        tree = RecordCaseCreationEvents(
            case_obj=VultronCase(
                id_="https://example.org/cases/tmp",
                name="Tmp Case",
                vulnerability_reports=[],
            )
        )
        assert isinstance(tree, py_trees.composites.Sequence)
        assert len(tree.children) == 2
        assert isinstance(tree.children[0], RecordOfferReceivedEventNode)
        assert isinstance(tree.children[1], RecordCaseCreatedEventNode)

    def test_record_offer_received_leaf_stages_case(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        case_obj: VultronCase,
        actor_id: str,
    ) -> None:
        result = bt_scenario.run(
            RecordOfferReceivedEventNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )
        bt_scenario.assert_success(result)
        staged_case = py_trees.blackboard.Blackboard.storage.get(
            "/case_for_creation_events"
        )
        assert getattr(staged_case, "id_", None) == case_obj.id_

    def test_record_case_created_leaf_persists_event(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        case_obj: VultronCase,
        actor_id: str,
    ) -> None:
        """RecordCaseCreatedEventNode returns SUCCESS when staged case exists.

        record_event('case_created') was removed in #789. The canonical ledger
        entry is now written by CommitCaseLedgerEntryNode at the end of the
        create_case tree. This node's sole responsibility is to read the staged
        case from the blackboard and confirm it is valid.
        """
        result = bt_scenario.run(
            RecordCaseCreatedEventNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
            case_for_creation_events=case_obj,
        )
        bt_scenario.assert_success(result)

    def test_record_offer_received_leaf_fails_without_case_id(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
    ) -> None:
        result = bt_scenario.run(
            RecordOfferReceivedEventNode(),
            actor_id=actor_id,
            # case_id intentionally omitted
        )
        # The missing required port *is* the subject here: a required input
        # was deliberately not supplied, so the tree fails via the port
        # contract rather than via a protocol decision (CONCERN-3019).
        bt_scenario.assert_failure(
            result, reason="Input port 'case_id'", allow_internal=True
        )

    def test_record_case_created_leaf_fails_without_staged_case(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        case_obj: VultronCase,
        actor_id: str,
    ) -> None:
        result = bt_scenario.run(
            RecordCaseCreatedEventNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
            # case_for_creation_events intentionally omitted
        )
        # The missing required port *is* the subject here: a required input
        # was deliberately not supplied, so the tree fails via the port
        # contract rather than via a protocol decision (CONCERN-3019).
        bt_scenario.assert_failure(
            result,
            reason="Input port 'case_for_creation_events'",
            allow_internal=True,
        )

    def test_activity_key_optional_node_succeeds_without_it(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        case_obj: VultronCase,
        actor_id: str,
    ) -> None:
        """Node runs successfully with no 'activity' on the blackboard.

        This behavioral test verifies BTND-03-001: if the 'activity' key were
        not properly registered by setup(), accessing it would raise
        AttributeError (unregistered) rather than being handled gracefully.
        Succeeding without an activity proves the key contract is correct.
        """
        result = bt_scenario.run(
            RecordCaseCreationEvents(case_obj=case_obj),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )
        bt_scenario.assert_success(result)

    def test_records_case_created_event_without_activity(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        case_obj: VultronCase,
        actor_id: str,
    ) -> None:
        """RecordCaseCreationEvents succeeds even without activity on blackboard.

        record_event('case_created') was removed in #789; the canonical commit
        is now done by CommitCaseLedgerEntryNode outside this subtree.
        This test verifies the node handles the no-activity case gracefully.
        """
        result = bt_scenario.run(
            RecordCaseCreationEvents(case_obj=case_obj),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )
        bt_scenario.assert_success(result)

    def test_records_offer_received_event_when_activity_has_in_reply_to(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        case_obj: VultronCase,
        report: VultronReport,
        actor_id: str,
    ) -> None:
        """RecordCaseCreationEvents succeeds when activity.in_reply_to is set.

        record_event('offer_received') was removed in #789. The triggering
        activity now serves as the canonical record via CommitCaseLedgerEntryNode.
        This test verifies the subtree handles in_reply_to gracefully.
        """
        offer_mock = MagicMock()
        offer_mock.id_ = "https://example.org/activities/offer-001"
        activity_mock = MagicMock()
        activity_mock.in_reply_to = offer_mock

        result = bt_scenario.run(
            RecordCaseCreationEvents(case_obj=case_obj),
            actor_id=actor_id,
            case_id=case_obj.id_,
            activity=activity_mock,
        )
        bt_scenario.assert_success(result)

    def test_no_offer_received_when_activity_lacks_in_reply_to(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        case_obj: VultronCase,
        actor_id: str,
    ) -> None:
        """RecordCaseCreationEvents succeeds when activity.in_reply_to is None.

        record_event calls were removed in #789. The subtree returns SUCCESS
        and does not write any case.events entries regardless of in_reply_to.
        """
        activity_mock = MagicMock()
        activity_mock.in_reply_to = None

        result = bt_scenario.run(
            RecordCaseCreationEvents(case_obj=case_obj),
            actor_id=actor_id,
            case_id=case_obj.id_,
            activity=activity_mock,
        )
        bt_scenario.assert_success(result)


# ---------------------------------------------------------------------------
# CreateCaseActorNode (blackboard variant) tests
# ---------------------------------------------------------------------------


class TestActorConfigCaseActorServiceUrl:
    """ActorConfig.case_actor_service_url field validation (CP-08-001)."""

    def test_defaults_to_none(self) -> None:
        """case_actor_service_url defaults to None when not configured."""
        from vultron.config.actor import ActorConfig

        cfg = ActorConfig()
        assert cfg.case_actor_service_url is None

    def test_accepts_valid_http_url(self) -> None:
        """case_actor_service_url accepts a valid HttpUrl string via model_validate."""
        from vultron.config.actor import ActorConfig

        cfg = ActorConfig.model_validate(
            {"case_actor_service_url": "http://case-actor:7999/api/v2"}
        )
        assert cfg.case_actor_service_url is not None
        assert "case-actor" in str(cfg.case_actor_service_url)

    def test_roundtrip_through_env_var(self, monkeypatch) -> None:
        """VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL sets case_actor_service_url."""
        from vultron.config.app import reload_config

        monkeypatch.setenv(
            "VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL",
            "http://case-actor:7999/api/v2",
        )
        reload_config()
        from vultron.config import get_config

        cfg = get_config().actor
        assert cfg.case_actor_service_url is not None
        assert "case-actor" in str(cfg.case_actor_service_url)
        reload_config()

    def test_construction_succeeds_without_field(self) -> None:
        """ActorConfig construction succeeds when case_actor_service_url absent."""
        from vultron.config.actor import ActorConfig

        cfg = ActorConfig(auto_create_case=True)
        assert cfg.case_actor_service_url is None


# ---------------------------------------------------------------------------
# ResolveCaseActorUrlsNode — trailing-slash normalisation (AC-2)
# ---------------------------------------------------------------------------


class TestProposeCaseToActorNode:
    """ProposeCaseToActorNode sends Create(as_CaseProposal) to the case-actor."""

    from vultron.core.behaviors.case.nodes.actor import (
        ProposeCaseToActorNode,
    )

    CASE_ACTOR_ID = "https://example.org/actors/case-actor-service"

    def test_succeeds_and_queues_proposal_to_outbox(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
        report: VultronReport,
        case_obj: VultronCase,
    ) -> None:
        """Happy path: node returns SUCCESS and enqueues a Create activity."""
        from vultron.core.behaviors.case.nodes.actor import (
            ProposeCaseToActorNode,
        )

        outbox_before = list(bt_scenario.dl.outbox_list() or [])
        result = bt_scenario.run(
            ProposeCaseToActorNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
            case_actor_id=self.CASE_ACTOR_ID,
        )
        bt_scenario.assert_success(result)

        outbox_after = list(bt_scenario.dl.outbox_list() or [])
        assert len(outbox_after) > len(
            outbox_before
        ), "ProposeCaseToActorNode must enqueue an activity to the outbox"

    def test_persists_create_activity_in_datalayer(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
        report: VultronReport,
        case_obj: VultronCase,
    ) -> None:
        """Create(as_CaseProposal) activity is persisted to the DataLayer."""
        from vultron.core.behaviors.case.nodes.actor import (
            ProposeCaseToActorNode,
        )

        create_activities_before = bt_scenario.dl.list_objects("Create")
        bt_scenario.run(
            ProposeCaseToActorNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
            case_actor_id=self.CASE_ACTOR_ID,
        )

        create_activities_after = bt_scenario.dl.list_objects("Create")
        assert len(create_activities_after) > len(
            create_activities_before
        ), "At least one new Create activity should be in the DataLayer"

    def test_fails_without_case_id(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
    ) -> None:
        """Node returns FAILURE when case_id is missing from the blackboard."""
        from vultron.core.behaviors.case.nodes.actor import (
            ProposeCaseToActorNode,
        )

        result = bt_scenario.run(
            ProposeCaseToActorNode(),
            actor_id=actor_id,
            case_actor_id=self.CASE_ACTOR_ID,
            # case_id intentionally omitted
        )
        bt_scenario.assert_failure(result)

    def test_fails_without_case_actor_id(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
        case_obj: VultronCase,
    ) -> None:
        """Node returns FAILURE when case_actor_id is missing from the blackboard."""
        from vultron.core.behaviors.case.nodes.actor import (
            ProposeCaseToActorNode,
        )

        result = bt_scenario.run(
            ProposeCaseToActorNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
            # case_actor_id intentionally omitted
        )
        bt_scenario.assert_failure(result)

    def test_fails_when_case_has_no_reports(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
    ) -> None:
        """Node returns FAILURE when the case has no linked VulnerabilityReport."""
        from vultron.core.behaviors.case.nodes.actor import (
            ProposeCaseToActorNode,
        )

        empty_case = VultronCase(
            id_="https://example.org/cases/empty-case",
            name="Empty Case",
            vulnerability_reports=[],
        )
        bt_scenario.dl.create(empty_case)

        result = bt_scenario.run(
            ProposeCaseToActorNode(),
            actor_id=actor_id,
            case_id=empty_case.id_,
            case_actor_id=self.CASE_ACTOR_ID,
        )
        bt_scenario.assert_failure(result)

    def test_fails_when_report_not_in_datalayer(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
    ) -> None:
        """Node returns FAILURE when the linked report is absent from DataLayer."""
        from vultron.core.behaviors.case.nodes.actor import (
            ProposeCaseToActorNode,
        )

        dangling_case = VultronCase(
            id_="https://example.org/cases/dangling",
            name="Dangling Case",
            vulnerability_reports=["https://example.org/reports/ghost"],
        )
        bt_scenario.dl.create(dangling_case)

        result = bt_scenario.run(
            ProposeCaseToActorNode(),
            actor_id=actor_id,
            case_id=dangling_case.id_,
            case_actor_id=self.CASE_ACTOR_ID,
        )
        bt_scenario.assert_failure(result)

    def test_fails_when_case_not_in_datalayer(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
    ) -> None:
        """Node returns FAILURE when the case record is absent from DataLayer."""
        from vultron.core.behaviors.case.nodes.actor import (
            ProposeCaseToActorNode,
        )

        result = bt_scenario.run(
            ProposeCaseToActorNode(),
            actor_id=actor_id,
            case_id="https://example.org/cases/nonexistent",
            case_actor_id=self.CASE_ACTOR_ID,
        )
        bt_scenario.assert_failure(result)

    def test_fails_when_no_trigger_activity_factory(
        self,
        actor: VultronCaseActor,
        actor_id: str,
        report: VultronReport,
        case_obj: VultronCase,
    ) -> None:
        """Node returns FAILURE when trigger_activity_factory is absent."""
        import py_trees

        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.case.nodes.actor import (
            ProposeCaseToActorNode,
        )

        # Build a bridge with NO trigger_activity_factory injected.
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        dl.create(actor)
        dl.create(report)
        dl.create(case_obj)
        bridge_no_factory = BTBridge(datalayer=dl)

        py_trees.blackboard.Blackboard.storage.clear()
        result = bridge_no_factory.execute_with_setup(
            tree=ProposeCaseToActorNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
            case_actor_id=self.CASE_ACTOR_ID,
        )
        assert result.status == py_trees.common.Status.FAILURE
