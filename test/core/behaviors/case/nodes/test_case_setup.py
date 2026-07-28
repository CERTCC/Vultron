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

import hashlib
from unittest.mock import MagicMock

import py_trees
import pytest

from vultron.core.behaviors.case.nodes import (
    CreateCaseActorNode,
    RecordCaseCreatedEventNode,
    RecordCaseCreationEvents,
    RecordOfferReceivedEventNode,
    UpdateActorOutbox,
)
from vultron.core.behaviors.case.nodes.case_setup import (
    CreateCaseActorServiceNode,
    RegisterCaseActorParticipantNode,
    ResolveCaseActorUrlsNode,
    ReuseExistingCaseActorParticipantNode,
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
        bt_scenario.assert_failure(result)

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
        bt_scenario.assert_failure(result)

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


class TestCreateCaseActorNodeBlackboard:
    """CreateCaseActorNode reads case_id from blackboard when not given at construction."""

    def test_creates_case_actor_from_blackboard_case_id(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
        case_obj: VultronCase,
    ) -> None:
        """CreateCaseActorNode() (no args) succeeds and creates a CaseActor entity."""
        result = bt_scenario.run(
            CreateCaseActorNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )
        bt_scenario.assert_success(result)

        # A Service (VultronCaseActor) should exist in the DataLayer.
        services = list(bt_scenario.dl.list_objects("Service"))
        case_actor_services = [
            s for s in services if getattr(s, "context", None) == case_obj.id_
        ]
        assert len(case_actor_services) >= 1

    def test_is_composed_subtree_of_named_leaf_nodes(self) -> None:
        node = CreateCaseActorNode()
        assert isinstance(node, py_trees.composites.Sequence)
        assert isinstance(node.children[0], ResolveCaseActorUrlsNode)
        assert isinstance(node.children[1], py_trees.composites.Selector)

        idempotency_selector = node.children[1]
        assert isinstance(
            idempotency_selector.children[0],
            ReuseExistingCaseActorParticipantNode,
        )
        create_branch = idempotency_selector.children[1]
        assert isinstance(create_branch, py_trees.composites.Sequence)
        assert [type(child) for child in create_branch.children] == [
            CreateCaseActorServiceNode,
            RegisterCaseActorParticipantNode,
        ]

    def test_writes_case_actor_id_to_blackboard(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
        case_obj: VultronCase,
    ) -> None:
        """CreateCaseActorNode() writes case_actor_id to the blackboard."""
        bt_scenario.run(
            CreateCaseActorNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )

        # py_trees stores global keys with a leading "/" prefix.
        stored = py_trees.blackboard.Blackboard.storage.get("/case_actor_id")
        assert stored is not None
        assert isinstance(stored, str)

    def test_registers_case_actor_participant(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
        case_obj: VultronCase,
    ) -> None:
        """CreateCaseActorNode registers a CASE_MANAGER participant in the case."""
        bt_scenario.run(
            CreateCaseActorNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )

        # Participant ID is derived from case_actor_service_url (CP-08-002).
        case_id = case_obj.id_
        if case_id.startswith("urn:uuid:"):
            case_slug = case_id[len("urn:uuid:") :]
        else:
            case_slug = hashlib.sha256(case_id.encode()).hexdigest()[:12]

        base_url = _CASE_ACTOR_SERVICE_URL.rstrip("/")
        expected_participant_id = (
            f"{base_url}/actors/case-actor-{case_slug}/participant"
        )
        participant = bt_scenario.dl.read(expected_participant_id)
        assert participant is not None

    def test_fails_without_case_id(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
    ) -> None:
        """CreateCaseActorNode() fails when case_id is not in blackboard."""
        result = bt_scenario.run(
            CreateCaseActorNode(),
            actor_id=actor_id,
            # No case_id supplied
        )
        assert result.status == py_trees.common.Status.FAILURE


# ---------------------------------------------------------------------------
# ResolveCaseActorUrlsNode — CP-08-002/003 unit tests (AC-7)
# ---------------------------------------------------------------------------


class TestResolveCaseActorUrlsNode:
    """ResolveCaseActorUrlsNode reads case_actor_service_url from ActorConfig."""

    def test_succeeds_with_configured_url(
        self,
        bt_scenario: BTTestScenario,
        actor_id: str,
        case_obj: VultronCase,
    ) -> None:
        """Returns SUCCESS and writes case_actor_id when URL is configured."""
        result = bt_scenario.run(
            ResolveCaseActorUrlsNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )
        assert result.status == py_trees.common.Status.SUCCESS

        stored_id = py_trees.blackboard.Blackboard.storage.get(
            "/case_actor_id"
        )
        assert stored_id is not None
        assert isinstance(stored_id, str)
        assert stored_id.startswith(_CASE_ACTOR_SERVICE_URL)

    def test_actor_id_uses_case_actor_service_url_not_server_base_url(
        self,
        bt_scenario: BTTestScenario,
        actor_id: str,
        case_obj: VultronCase,
        monkeypatch,
    ) -> None:
        """case_actor_id is derived from case_actor_service_url, not server.base_url."""
        from vultron.config.app import reload_config

        monkeypatch.setenv(
            "VULTRON_SERVER__BASE_URL", "http://vendor:7999/api/v2"
        )
        reload_config()

        result = bt_scenario.run(
            ResolveCaseActorUrlsNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )
        assert result.status == py_trees.common.Status.SUCCESS

        stored_id = py_trees.blackboard.Blackboard.storage.get(
            "/case_actor_id"
        )
        assert stored_id is not None
        assert stored_id.startswith(_CASE_ACTOR_SERVICE_URL)
        assert "vendor" not in stored_id

    def test_fails_when_case_actor_service_url_is_none(
        self,
        bt_scenario: BTTestScenario,
        actor_id: str,
        case_obj: VultronCase,
        monkeypatch,
    ) -> None:
        """Returns FAILURE with a log message when case_actor_service_url is None."""
        from vultron.config.app import reload_config

        monkeypatch.delenv(
            "VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL", raising=False
        )
        reload_config()

        result = bt_scenario.run(
            ResolveCaseActorUrlsNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )
        assert result.status == py_trees.common.Status.FAILURE

    def test_fails_without_case_id(
        self,
        bt_scenario: BTTestScenario,
        actor_id: str,
    ) -> None:
        """Returns FAILURE when case_id is absent from blackboard."""
        result = bt_scenario.run(
            ResolveCaseActorUrlsNode(),
            actor_id=actor_id,
        )
        assert result.status == py_trees.common.Status.FAILURE

    def test_server_base_url_not_registered_in_setup(
        self,
        actor_id: str,
        case_obj: VultronCase,
    ) -> None:
        """setup() must NOT register server_base_url as a blackboard key."""
        import py_trees
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.behaviors.bridge import BTBridge

        dl = SqliteDataLayer("sqlite:///:memory:")
        bridge = BTBridge(datalayer=dl)
        node = ResolveCaseActorUrlsNode()
        bt = bridge.setup_tree(node, actor_id=actor_id, case_id=case_obj.id_)
        bt.setup()

        # server_base_url must not be registered after setup.
        all_keys = {
            k.lstrip("/") for k in py_trees.blackboard.Blackboard.storage
        }
        assert "server_base_url" not in all_keys


# ---------------------------------------------------------------------------
# ActorConfig — case_actor_service_url field tests (AC-7a)
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


class TestResolveCaseActorUrlsNodeTrailingSlash:
    """case_actor_service_url with a trailing slash must not produce double-slash IDs."""

    CASE_ID = "urn:uuid:trailing-slash-test"

    def test_trailing_slash_in_url_does_not_double_slash_actor_id(
        self, bt_scenario: BTTestScenario, monkeypatch
    ) -> None:
        from vultron.config.app import reload_config

        monkeypatch.setenv(
            "VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL",
            "http://case-actor:7999/api/v2/",  # trailing slash
        )
        reload_config()
        result = bt_scenario.run(
            ResolveCaseActorUrlsNode(case_id=self.CASE_ID),
        )
        bt_scenario.assert_success(result)
        case_actor_id = py_trees.blackboard.Blackboard.storage.get(
            "/case_actor_id"
        )
        assert case_actor_id is not None
        assert (
            "//" not in case_actor_id.split("://", 1)[-1]
        ), f"Double-slash in actor ID: {case_actor_id!r}"


# ---------------------------------------------------------------------------
# RegisterCaseActorParticipantNode — precondition failure tests
# ---------------------------------------------------------------------------


class TestRegisterCaseActorParticipantNode:
    """RegisterCaseActorParticipantNode returns FAILURE when case is absent."""

    def test_fails_when_case_not_in_datalayer(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
    ) -> None:
        """Node returns FAILURE (not SUCCESS) when the case record is missing."""
        result = bt_scenario.run(
            RegisterCaseActorParticipantNode(),
            actor_id=actor_id,
            case_id="https://example.org/cases/nonexistent",
            case_actor_id=f"{actor_id}/case-actor",
            case_actor_participant_id=f"{actor_id}/case-actor/participant",
        )
        assert result.status == py_trees.common.Status.FAILURE


# ---------------------------------------------------------------------------
# ProposeCaseToActorNode tests
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

        outbox_before = list(
            bt_scenario.dl.outbox_list_for_actor(actor_id) or []
        )
        result = bt_scenario.run(
            ProposeCaseToActorNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
            case_actor_id=self.CASE_ACTOR_ID,
        )
        bt_scenario.assert_success(result)

        outbox_after = list(
            bt_scenario.dl.outbox_list_for_actor(actor_id) or []
        )
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
        dl = SqliteDataLayer("sqlite:///:memory:")
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
