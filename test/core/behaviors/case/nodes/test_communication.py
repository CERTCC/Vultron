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

Covers EmitCreateCaseActivity and related leaf nodes.
"""

import py_trees
import pytest

from vultron.core.behaviors.case.nodes import (
    CollectCaseAddresseesNode,
    CreateAndPersistCaseActivityNode,
    EmitCreateCaseActivity,
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
    """Set VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL for this module.

    ``CreateCaseActorNode`` runs ``ResolveCaseActorUrlsNode``, which returns
    FAILURE when ``case_actor_service_url`` is None (CP-08-002/003).  This
    module used to inherit the value leaked into the module-level config cache
    by another test's fixture, so it failed whenever it ran in isolation or in
    a subset (#1897).  Configuring it here makes the module self-sufficient.
    """
    from vultron.config.app import reload_config

    monkeypatch.setenv(
        "VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL", _CASE_ACTOR_SERVICE_URL
    )
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
