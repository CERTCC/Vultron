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
"""Unit tests for vultron/demo/fuzzer/embargo.py.

Tests cover:
  - All 15 nodes are WeightedBehavior subclasses
  - Each node has the correct success_rate attribute (AC-1, AC-3)
  - Each node has a non-empty docstring covering semantic function,
    input category, success probability, and automation potential (AC-2)
  - update() returns only valid Status values
  - AlwaysSucceed-based nodes always succeed
  - AlwaysFail-based nodes never succeed
  - Empirical distribution checks for selected nodes
"""

import random
from typing import Type

import py_trees
import pytest
from py_trees.common import Status

from vultron.demo.fuzzer.base import WeightedBehavior
from vultron.demo.fuzzer.embargo import (
    AvoidEmbargoCounterProposal,
    CurrentEmbargoAcceptable,
    EmbargoTimerExpired,
    EvaluateEmbargoProposal,
    ExitEmbargoForOtherReason,
    ExitEmbargoWhenDeployed,
    ExitEmbargoWhenFixReady,
    OnEmbargoAccept,
    OnEmbargoExit,
    OnEmbargoReject,
    ReasonToProposeEmbargoWhenDeployed,
    SelectEmbargoOfferTerms,
    StopProposingEmbargo,
    WantToProposeEmbargo,
    WillingToCounterEmbargoProposal,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TRIALS = 10_000
_TOLERANCE = 0.03  # ±3 percentage points

# All 15 nodes with their expected success_rates
_ALL_NODES: list[tuple[Type[WeightedBehavior], float]] = [
    (ExitEmbargoWhenDeployed, 1.0 / 3.0),
    (ExitEmbargoWhenFixReady, 1.0 / 4.0),
    (ExitEmbargoForOtherReason, 1.0 / 200.0),
    (EmbargoTimerExpired, 1.0 / 100.0),
    (OnEmbargoExit, 1.0),
    (StopProposingEmbargo, 1.0 / 4.0),
    (SelectEmbargoOfferTerms, 1.0),
    (WantToProposeEmbargo, 1.0 / 2.0),
    (WillingToCounterEmbargoProposal, 1.0 / 4.0),
    (AvoidEmbargoCounterProposal, 3.0 / 4.0),
    (ReasonToProposeEmbargoWhenDeployed, 7.0 / 100.0),
    (EvaluateEmbargoProposal, 3.0 / 4.0),
    (OnEmbargoAccept, 1.0),
    (OnEmbargoReject, 1.0),
    (CurrentEmbargoAcceptable, 9.0 / 10.0),
]

_NODE_NAMES = [cls.__name__ for cls, _ in _ALL_NODES]


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
# AC-1: All 15 nodes ported using py_trees base types
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
        node = cls()
        assert isinstance(node, py_trees.behaviour.Behaviour)

    @pytest.mark.parametrize("cls,_rate", _ALL_NODES)
    def test_default_name_is_class_name(
        self, cls: Type[WeightedBehavior], _rate: float
    ) -> None:
        node = cls()
        assert node.name == cls.__name__

    def test_all_15_nodes_present(self) -> None:
        assert (
            len(_ALL_NODES) == 15
        ), f"Expected 15 embargo fuzzer nodes, found {len(_ALL_NODES)}"


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

    @pytest.mark.parametrize("cls,_rate", _ALL_NODES)
    def test_docstring_mentions_semantic_function(
        self, cls: Type[WeightedBehavior], _rate: float
    ) -> None:
        doc = (cls.__doc__ or "").lower()
        assert (
            "semantic function" in doc
        ), f"{cls.__name__} docstring missing 'Semantic function' section"

    @pytest.mark.parametrize("cls,_rate", _ALL_NODES)
    def test_docstring_mentions_input_category(
        self, cls: Type[WeightedBehavior], _rate: float
    ) -> None:
        doc = (cls.__doc__ or "").lower()
        assert (
            "input category" in doc
        ), f"{cls.__name__} docstring missing 'Input category' section"

    @pytest.mark.parametrize("cls,_rate", _ALL_NODES)
    def test_docstring_mentions_success_probability(
        self, cls: Type[WeightedBehavior], _rate: float
    ) -> None:
        doc = (cls.__doc__ or "").lower()
        assert (
            "success probability" in doc
        ), f"{cls.__name__} docstring missing 'Success probability' section"

    @pytest.mark.parametrize("cls,_rate", _ALL_NODES)
    def test_docstring_mentions_automation_potential(
        self, cls: Type[WeightedBehavior], _rate: float
    ) -> None:
        doc = (cls.__doc__ or "").lower()
        assert (
            "automation potential" in doc
        ), f"{cls.__name__} docstring missing 'Automation potential' section"


# ---------------------------------------------------------------------------
# AC-3: Unit tests verify correct status distribution
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
        assert result in (
            Status.SUCCESS,
            Status.FAILURE,
        ), f"{cls.__name__}.update() returned unexpected status: {result}"

    @pytest.mark.parametrize("cls,_rate", _ALL_NODES)
    def test_update_never_returns_running(
        self, cls: Type[WeightedBehavior], _rate: float
    ) -> None:
        node = cls()
        node.setup()
        results = {node.update() for _ in range(50)}
        assert (
            Status.RUNNING not in results
        ), f"{cls.__name__}.update() returned RUNNING unexpectedly"


class TestDeterministicExtremes:
    def test_on_embargo_exit_always_succeeds(self) -> None:
        node = OnEmbargoExit()
        node.setup()
        assert all(node.update() == Status.SUCCESS for _ in range(100))

    def test_select_embargo_offer_terms_always_succeeds(self) -> None:
        node = SelectEmbargoOfferTerms()
        node.setup()
        assert all(node.update() == Status.SUCCESS for _ in range(100))

    def test_on_embargo_accept_always_succeeds(self) -> None:
        node = OnEmbargoAccept()
        node.setup()
        assert all(node.update() == Status.SUCCESS for _ in range(100))

    def test_on_embargo_reject_always_succeeds(self) -> None:
        node = OnEmbargoReject()
        node.setup()
        assert all(node.update() == Status.SUCCESS for _ in range(100))


class TestEmpiricalDistributions:
    """Verify that probabilistic nodes produce the expected distribution."""

    @pytest.mark.parametrize(
        "cls,expected_rate",
        [
            (ExitEmbargoWhenDeployed, 1.0 / 3.0),
            (ExitEmbargoWhenFixReady, 1.0 / 4.0),
            (WantToProposeEmbargo, 0.50),
            (AvoidEmbargoCounterProposal, 0.75),
            (EvaluateEmbargoProposal, 0.75),
            (CurrentEmbargoAcceptable, 0.90),
        ],
    )
    def test_empirical_distribution(
        self, cls: Type[WeightedBehavior], expected_rate: float
    ) -> None:
        rate = _run_trials(cls)
        assert (
            abs(rate - expected_rate) < _TOLERANCE
        ), f"{cls.__name__}: empirical={rate:.4f} expected={expected_rate:.4f}"

    def test_seeded_determinism(self) -> None:
        """Same seed → same sequence for a representative node."""
        random.seed(42)
        node = EvaluateEmbargoProposal()
        node.setup()
        seq_a = [node.update() for _ in range(20)]
        random.seed(42)
        seq_b = [node.update() for _ in range(20)]
        assert seq_a == seq_b


# ---------------------------------------------------------------------------
# Invariant: AvoidEmbargoCounterProposal is complement of WillingToCounter
# ---------------------------------------------------------------------------


class TestAvoidCounterIsComplementOfWillingToCounter:
    def test_success_rates_sum_to_one(self) -> None:
        assert (
            abs(
                WillingToCounterEmbargoProposal.success_rate
                + AvoidEmbargoCounterProposal.success_rate
                - 1.0
            )
            < 1e-9
        )

    def test_empirical_rates_are_complementary(self) -> None:
        willing_rate = _run_trials(WillingToCounterEmbargoProposal)
        avoid_rate = _run_trials(AvoidEmbargoCounterProposal)
        assert abs(willing_rate + avoid_rate - 1.0) < (2 * _TOLERANCE)
