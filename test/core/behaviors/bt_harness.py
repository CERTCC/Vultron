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
BTTestScenario — deep-module test harness for Behavior Tree tests.

Encapsulates the correct BTBridge path for all BT tests (leaf nodes and
composite trees alike). Eliminates duplicated ``setup_node_blackboard()``
boilerplate that bypasses the proper BT lifecycle.

Per specs/testability.yaml TB-06 requirements and GitHub issue #401.

Usage
-----
.. code-block:: python

    def test_example(bt_scenario, report, offer):
        result = bt_scenario.run(TransitionRMtoValid(report_id=report.id_, offer_id=offer.id_))
        bt_scenario.assert_success(result)
        bt_scenario.assert_rm_state(report.id_, RM.VALID, actor_id=actor.id_)
"""

from __future__ import annotations

from typing import Any, Callable, cast

import py_trees
import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.behaviors.bridge import BTBridge, BTExecutionResult
from vultron.core.states.rm import RM
from vultron.core.use_cases._helpers import _report_phase_status_id


class BTTestScenario:
    """Deep-module harness for BT test scenarios.

    Provides the single correct execution path for all BT tests: leaf nodes
    and composite trees alike. Eliminates duplicated blackboard-setup
    boilerplate and ensures every test exercises the real BTBridge lifecycle
    (setup → initialise → update → shutdown).

    Attributes:
        actor_id: Default actor ID used when none is supplied to ``run()``.
        dl: In-memory SQLite DataLayer shared across all seed/run/assert calls.
        bridge: ``BTBridge`` wired to ``dl``.
    """

    def __init__(
        self,
        actor_id: str = "https://example.org/actors/vendor",
        *,
        dl: SqliteDataLayer | None = None,
        is_leader: bool = True,
    ) -> None:
        self.actor_id = actor_id
        self.dl = dl or SqliteDataLayer("sqlite:///:memory:")
        self.bridge = BTBridge(
            datalayer=self.dl,
            is_leader=lambda: is_leader,
            trigger_activity=TriggerActivityAdapter(self.dl),
        )

    # ------------------------------------------------------------------
    # Precondition setup
    # ------------------------------------------------------------------

    def seed(self, *objects: Any) -> "BTTestScenario":
        """Persist domain objects as preconditions; returns self for chaining.

        Args:
            *objects: Persistable domain objects to create in the DataLayer.

        Returns:
            self, enabling method chaining.
        """
        for obj in objects:
            self.dl.create(obj)
        return self

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run(
        self,
        tree: py_trees.behaviour.Behaviour,
        actor_id: str | None = None,
        activity: Any = None,
        **context_data: Any,
    ) -> BTExecutionResult:
        """Execute a node or tree through BTBridge; clears blackboard first.

        Args:
            tree: Root behavior node or composite tree to execute.
            actor_id: Actor ID to bind on the blackboard; defaults to
                ``self.actor_id``.
            activity: Optional ActivityStreams activity being processed.
            **context_data: Additional key/value pairs to populate on the
                blackboard (e.g., ``case_id="https://..."``).

        Returns:
            BTExecutionResult with status, feedback, and any errors.
        """
        py_trees.blackboard.Blackboard.storage.clear()
        return self.bridge.execute_with_setup(
            tree=tree,
            actor_id=actor_id if actor_id is not None else self.actor_id,
            activity=activity,
            **context_data,
        )

    # ------------------------------------------------------------------
    # Status assertions
    # ------------------------------------------------------------------

    def assert_success(self, result: BTExecutionResult) -> None:
        """Assert that the execution result is SUCCESS.

        Args:
            result: BTExecutionResult to check.
        """
        assert (
            result.status == py_trees.common.Status.SUCCESS
        ), f"Expected SUCCESS but got {result.status}: {result.feedback_message}"

    def assert_failure(self, result: BTExecutionResult) -> None:
        """Assert that the execution result is FAILURE.

        Args:
            result: BTExecutionResult to check.
        """
        assert (
            result.status == py_trees.common.Status.FAILURE
        ), f"Expected FAILURE but got {result.status}: {result.feedback_message}"

    def assert_failure_reason(
        self,
        tree: py_trees.behaviour.Behaviour,
        expected_substr: str,
    ) -> None:
        """Assert that the first FAILURE node's message contains expected_substr.

        Args:
            tree: Root behavior node to inspect (after a failed run).
            expected_substr: Substring expected in the failure reason.
        """
        reason = BTBridge.get_failure_reason(tree)
        assert (
            expected_substr in reason
        ), f"Expected {expected_substr!r} in failure reason, got {reason!r}"

    # ------------------------------------------------------------------
    # DataLayer assertions
    # ------------------------------------------------------------------

    def assert_object_in_dl(
        self, obj_id: str, type_key: str | None = None
    ) -> Any:
        """Assert object exists in the DataLayer; return it.

        Args:
            obj_id: ID of the object to look up.
            type_key: Optional type key for additional membership check.

        Returns:
            The stored object.
        """
        obj = self.dl.read(obj_id)
        assert obj is not None, f"Expected object {obj_id!r} in DataLayer"
        if type_key is not None:
            records = self.dl.by_type(type_key)
            assert (
                obj_id in records
            ), f"Expected object {obj_id!r} of type {type_key!r} in DataLayer"
        return obj

    def assert_object_absent(self, obj_id: str) -> None:
        """Assert that an object does NOT exist in the DataLayer.

        Args:
            obj_id: ID of the object that must be absent.
        """
        obj = self.dl.read(obj_id)
        assert (
            obj is None
        ), f"Expected object {obj_id!r} to be absent from DataLayer"

    def assert_type_count(self, type_key: str, expected: int) -> None:
        """Assert the DataLayer contains exactly ``expected`` objects of type.

        Args:
            type_key: Type discriminator string (e.g., ``"VulnerabilityCase"``).
            expected: Expected number of matching records.
        """
        actual = len(self.dl.by_type(type_key))
        assert (
            actual == expected
        ), f"Expected {expected} object(s) of type {type_key!r}, got {actual}"

    # ------------------------------------------------------------------
    # Domain assertions
    # ------------------------------------------------------------------

    def assert_rm_state(
        self,
        report_id: str,
        expected_rm: RM,
        actor_id: str | None = None,
    ) -> None:
        """Assert that a RM-state record exists for the given actor and report.

        Uses ``_report_phase_status_id`` to derive the deterministic record
        ID, then verifies the record is present in the DataLayer.

        Args:
            report_id: Report ID.
            expected_rm: Expected RM enum value (e.g., ``RM.VALID``).
            actor_id: Actor ID; defaults to ``self.actor_id``.
        """
        actor = actor_id if actor_id is not None else self.actor_id
        status_id = _report_phase_status_id(
            actor, report_id, expected_rm.value
        )
        obj = self.dl.read(status_id)
        assert obj is not None, (
            f"Expected RM state {expected_rm!r} for report {report_id!r} "
            f"actor {actor!r} not found in DataLayer (looked up id={status_id!r})"
        )

    def assert_case_count(self, expected: int) -> None:
        """Assert exactly ``expected`` VulnerabilityCase objects in DataLayer.

        Args:
            expected: Expected case count.
        """
        self.assert_type_count("VulnerabilityCase", expected)

    def assert_case_exists(self) -> Any:
        """Assert exactly one VulnerabilityCase in DataLayer and return it.

        Returns:
            The single VulnerabilityCase object.

        Raises:
            AssertionError: If there is not exactly one VulnerabilityCase.
        """
        cases = self.dl.by_type("VulnerabilityCase")
        assert (
            len(cases) == 1
        ), f"Expected exactly 1 VulnerabilityCase in DataLayer, found {len(cases)}"
        case_id = next(iter(cases))
        case = self.dl.read(case_id)
        assert case is not None, (
            "Expected VulnerabilityCase id "
            f"{case_id!r} from DataLayer.by_type('VulnerabilityCase') "
            "to be readable, but DataLayer.read() returned None"
        )
        return cast(Any, case)

    def assert_note_attached_to_case(self, note_id: str, case_id: str) -> None:
        """Assert that ``note_id`` appears in the case's notes list.

        Args:
            note_id: ID of the note to look for.
            case_id: ID of the VulnerabilityCase to inspect.
        """
        case = cast(Any, self.dl.read(case_id))
        assert case is not None, f"Case {case_id!r} not found in DataLayer"
        assert (
            note_id in case.notes
        ), f"Note {note_id!r} not attached to case {case_id!r}"

    def assert_participant_in_case(self, actor_id: str, case_id: str) -> None:
        """Assert that ``actor_id`` appears in the case's participant index.

        Args:
            actor_id: Actor ID expected as a case participant.
            case_id: ID of the VulnerabilityCase to inspect.
        """
        case = cast(Any, self.dl.read(case_id))
        assert case is not None, f"Case {case_id!r} not found in DataLayer"
        assert (
            actor_id in case.actor_participant_index
        ), f"Actor {actor_id!r} is not a participant in case {case_id!r}"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def bt_scenario() -> BTTestScenario:
    """Return a BTTestScenario with a fresh in-memory DataLayer."""
    return BTTestScenario()


@pytest.fixture
def bt_scenario_factory() -> Callable[..., BTTestScenario]:
    """Return a factory for BTTestScenario instances.

    The factory signature is:
    ``factory(actor_id=..., *, dl=None, is_leader=True) -> BTTestScenario``

    This is useful when a test needs multiple scenario instances (e.g.,
    leadership-guard rejection tests or multi-actor scenarios with a shared
    DataLayer).
    """

    def _factory(
        actor_id: str = "https://example.org/actors/vendor",
        *,
        dl: SqliteDataLayer | None = None,
        is_leader: bool = True,
    ) -> BTTestScenario:
        return BTTestScenario(actor_id=actor_id, dl=dl, is_leader=is_leader)

    return _factory


@pytest.fixture
def shared_dl_actors() -> tuple[BTTestScenario, BTTestScenario]:
    """Return two BTTestScenario instances (vendor + reporter) sharing one DL.

    Both ``VultronCaseActor`` objects are persisted in the shared DataLayer
    so BT nodes that look up actor records can find them.
    """
    from vultron.core.models.case_actor import VultronCaseActor

    dl = SqliteDataLayer("sqlite:///:memory:")
    vendor_id = "https://example.org/actors/vendor"
    reporter_id = "https://example.org/actors/reporter"

    vendor_actor = VultronCaseActor(id_=vendor_id, name="Vendor Co")
    reporter_actor = VultronCaseActor(id_=reporter_id, name="Reporter Co")
    dl.create(vendor_actor)
    dl.create(reporter_actor)

    vendor = BTTestScenario(actor_id=vendor_id, dl=dl)
    reporter = BTTestScenario(actor_id=reporter_id, dl=dl)
    return vendor, reporter
