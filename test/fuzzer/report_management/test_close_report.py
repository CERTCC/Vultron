#!/usr/bin/env python
#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
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
"""Unit tests for vultron/demo/fuzzer/report_management/close_report.py.

Tests cover:
  - Both nodes are WeightedBehavior subclasses (AC-1)
  - Each node has a non-empty docstring covering required sections (AC-2)
  - Correct success_rate attributes and status distribution (AC-3)
  - AlwaysSucceed-based nodes always succeed
  - Empirical distribution check for OtherCloseCriteriaMet
"""

import py_trees
import pytest
from py_trees.common import Status
from typing import Type

from vultron.demo.fuzzer.base import WeightedBehavior
from vultron.demo.fuzzer.report_management.close_report import (
    OtherCloseCriteriaMet,
    PreCloseAction,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TRIALS = 10_000
_TOLERANCE = 0.03  # ±3 percentage points

_ALL_NODES: list[tuple[Type[WeightedBehavior], float]] = [
    (OtherCloseCriteriaMet, 1.0 / 4.0),
    (PreCloseAction, 1.0),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_trials(node_cls: Type[WeightedBehavior], n: int = _TRIALS) -> float:
    """Return empirical success rate over *n* independent ticks."""
    node = node_cls()
    node.setup()
    successes = sum(1 for _ in range(n) if node.update() == Status.SUCCESS)
    return successes / n


# ---------------------------------------------------------------------------
# AC-1: All 2 nodes use py_trees base types
# ---------------------------------------------------------------------------


class TestAllNodesAreWeightedBehavior:
    @pytest.mark.parametrize("cls,_rate", _ALL_NODES)
    def test_is_weighted_behavior_subclass(
        self, cls: Type[WeightedBehavior], _rate: float
    ) -> None:
        assert issubclass(
            cls, WeightedBehavior
        ), f"{cls.__name__} must be a WeightedBehavior subclass"

    @pytest.mark.parametrize("cls,_rate", _ALL_NODES)
    def test_is_py_trees_behaviour(
        self, cls: Type[WeightedBehavior], _rate: float
    ) -> None:
        assert isinstance(cls(), py_trees.behaviour.Behaviour)

    @pytest.mark.parametrize("cls,_rate", _ALL_NODES)
    def test_default_name_is_class_name(
        self, cls: Type[WeightedBehavior], _rate: float
    ) -> None:
        assert cls().name == cls.__name__

    def test_all_2_nodes_present(self) -> None:
        assert (
            len(_ALL_NODES) == 2
        ), f"Expected 2 close-report fuzzer nodes, found {len(_ALL_NODES)}"


# ---------------------------------------------------------------------------
# AC-2: Docstrings cover required fields per BT-16-003 / BT-16-005
# ---------------------------------------------------------------------------


class TestDocstrings:
    @pytest.mark.parametrize("cls,_rate", _ALL_NODES)
    def test_has_non_empty_docstring(
        self, cls: Type[WeightedBehavior], _rate: float
    ) -> None:
        doc = cls.__doc__ or ""
        assert len(doc.strip()) > 0, f"{cls.__name__} has an empty docstring"

    @pytest.mark.parametrize(
        "cls,_rate,section",
        [
            (cls, rate, section)
            for cls, rate in _ALL_NODES
            for section in [
                "semantic function",
                "input category",
                "success probability",
                "automation potential",
            ]
        ],
    )
    def test_docstring_has_required_section(
        self, cls: Type[WeightedBehavior], _rate: float, section: str
    ) -> None:
        doc = (cls.__doc__ or "").lower()
        assert (
            section in doc
        ), f"{cls.__name__} docstring missing '{section}' section"


# ---------------------------------------------------------------------------
# AC-3: success_rate attributes and status distribution
# ---------------------------------------------------------------------------


class TestSuccessRateAttributes:
    @pytest.mark.parametrize("cls,expected_rate", _ALL_NODES)
    def test_success_rate_attribute(
        self, cls: Type[WeightedBehavior], expected_rate: float
    ) -> None:
        assert abs(cls.success_rate - expected_rate) < 1e-9, (
            f"{cls.__name__}: success_rate={cls.success_rate!r}, "
            f"expected {expected_rate!r}"
        )


class TestUpdateReturnsValidStatus:
    @pytest.mark.parametrize("cls,_rate", _ALL_NODES)
    def test_update_returns_success_or_failure(
        self, cls: Type[WeightedBehavior], _rate: float
    ) -> None:
        node = cls()
        node.setup()
        result = node.update()
        assert result in (Status.SUCCESS, Status.FAILURE)

    @pytest.mark.parametrize("cls,_rate", _ALL_NODES)
    def test_update_never_returns_running(
        self, cls: Type[WeightedBehavior], _rate: float
    ) -> None:
        node = cls()
        node.setup()
        results = {node.update() for _ in range(50)}
        assert Status.RUNNING not in results


class TestDeterministicExtremes:
    def test_pre_close_action_always_succeeds(self) -> None:
        node = PreCloseAction()
        node.setup()
        assert all(node.update() == Status.SUCCESS for _ in range(100))


class TestEmpiricalDistributions:
    def test_other_close_criteria_met_distribution(self) -> None:
        rate = _run_trials(OtherCloseCriteriaMet)
        expected = 1.0 / 4.0
        assert abs(rate - expected) < _TOLERANCE, (
            f"OtherCloseCriteriaMet: empirical={rate:.4f} "
            f"expected={expected:.4f}"
        )
