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
Tests for the BTTestScenario harness itself.

Covers:
- bt_scenario_factory: leadership guard (SYNC-09-003), custom actor IDs, shared DL
- shared_dl_actors: multi-actor shared DataLayer fixture
"""

from typing import Callable

import py_trees

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from test.core.behaviors.bt_harness import BTTestScenario


class TestBTScenarioFactory:
    """Tests for the bt_scenario_factory fixture (SYNC-09-003 leadership guard)."""

    def test_non_leader_returns_failure(
        self,
        bt_scenario_factory: Callable[..., BTTestScenario],
    ) -> None:
        """When is_leader=False, execute_with_setup returns FAILURE immediately."""
        scenario = bt_scenario_factory(is_leader=False)
        node = py_trees.behaviours.Success("dummy")
        result = scenario.bridge.execute_with_setup(
            node, actor_id=scenario.actor_id
        )
        assert result.status == py_trees.common.Status.FAILURE
        assert "not the replication leader" in result.feedback_message

    def test_leader_returns_success(
        self,
        bt_scenario_factory: Callable[..., BTTestScenario],
    ) -> None:
        """When is_leader=True (default), a Success node returns SUCCESS."""
        scenario = bt_scenario_factory(is_leader=True)
        node = py_trees.behaviours.Success("dummy")
        result = scenario.bridge.execute_with_setup(
            node, actor_id=scenario.actor_id
        )
        assert result.status == py_trees.common.Status.SUCCESS

    def test_custom_actor_id(
        self,
        bt_scenario_factory: Callable[..., BTTestScenario],
    ) -> None:
        """Factory respects the actor_id argument."""
        custom_id = "https://example.org/actors/custom"
        scenario = bt_scenario_factory(actor_id=custom_id)
        assert scenario.actor_id == custom_id

    def test_shared_dl_parameter(
        self,
        bt_scenario_factory: Callable[..., BTTestScenario],
    ) -> None:
        """Two factory instances created with the same dl share data."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        s1 = bt_scenario_factory(
            actor_id="https://example.org/actors/a1", dl=dl
        )
        s2 = bt_scenario_factory(
            actor_id="https://example.org/actors/a2", dl=dl
        )
        assert s1.dl is s2.dl


class TestSharedDlActors:
    """Tests for the shared_dl_actors fixture (multi-actor shared DataLayer)."""

    def test_both_scenarios_share_same_dl(
        self,
        shared_dl_actors: tuple[BTTestScenario, BTTestScenario],
    ) -> None:
        """vendor and reporter operate on the same DataLayer instance."""
        vendor, reporter = shared_dl_actors
        assert vendor.dl is reporter.dl

    def test_vendor_actor_persisted(
        self,
        shared_dl_actors: tuple[BTTestScenario, BTTestScenario],
    ) -> None:
        """Vendor actor record is readable from the shared DataLayer."""
        vendor, _ = shared_dl_actors
        record = vendor.dl.read(vendor.actor_id)
        assert record is not None

    def test_reporter_actor_persisted(
        self,
        shared_dl_actors: tuple[BTTestScenario, BTTestScenario],
    ) -> None:
        """Reporter actor record is readable from the shared DataLayer."""
        _, reporter = shared_dl_actors
        record = reporter.dl.read(reporter.actor_id)
        assert record is not None

    def test_reporter_visible_from_vendor_dl(
        self,
        shared_dl_actors: tuple[BTTestScenario, BTTestScenario],
    ) -> None:
        """Reporter actor is visible when looked up via vendor's DataLayer."""
        vendor, reporter = shared_dl_actors
        record = vendor.dl.read(reporter.actor_id)
        assert record is not None

    def test_distinct_actor_ids(
        self,
        shared_dl_actors: tuple[BTTestScenario, BTTestScenario],
    ) -> None:
        """Vendor and reporter have different actor IDs."""
        vendor, reporter = shared_dl_actors
        assert vendor.actor_id != reporter.actor_id
