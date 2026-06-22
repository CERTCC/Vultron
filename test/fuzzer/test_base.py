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
"""Unit tests for vultron/demo/fuzzer/base.py.

Tests cover:
  - WeightedBehavior: correct status distribution at known probabilities
  - SuccessOrRunning: never returns FAILURE
  - AlwaysSucceed / AlwaysFail: deterministic outcomes
  - All probability subclasses: correct success_rate attribute
  - Aliases: LikelyFail, LikelySucceed, RarelySucceed, RandomSucceedFail,
    RandomConditionNode, RandomActionNode point to expected concrete classes
  - Package re-exports: all public names accessible from vultron.demo.fuzzer
"""

import random
from typing import Type

import pytest

from vultron.demo.fuzzer.base import (
    AlmostAlwaysFail,
    AlmostAlwaysSucceed,
    AlmostCertainlyFail,
    AlmostCertainlySucceed,
    AlwaysFail,
    AlwaysSucceed,
    LikelyFail,
    LikelySucceed,
    OftenFail,
    OftenSucceed,
    OneInOneHundred,
    OneInTwenty,
    OneInTwoHundred,
    ProbablyFail,
    ProbablySucceed,
    RandomActionNode,
    RandomConditionNode,
    RandomSucceedFail,
    RarelySucceed,
    SuccessOrRunning,
    UniformSucceedFail,
    UsuallyFail,
    UsuallySucceed,
    WeightedBehavior,
)
from py_trees.common import Status

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TRIALS = 10_000
_TOLERANCE = 0.03  # ±3 percentage points


def _run_trials(node_cls: Type[WeightedBehavior], n: int = _TRIALS) -> float:
    """Return empirical success rate over *n* independent ticks."""
    node = node_cls()
    successes = sum(1 for _ in range(n) if node.update() == Status.SUCCESS)
    return successes / n


# ---------------------------------------------------------------------------
# WeightedBehavior base
# ---------------------------------------------------------------------------


class TestWeightedBehavior:
    def test_is_py_trees_behaviour(self) -> None:
        import py_trees

        node = WeightedBehavior()
        assert isinstance(node, py_trees.behaviour.Behaviour)

    def test_default_name_is_class_name(self) -> None:
        node = WeightedBehavior()
        assert node.name == "WeightedBehavior"

    def test_custom_name_is_preserved(self) -> None:
        node = WeightedBehavior(name="my_node")
        assert node.name == "my_node"

    def test_default_success_rate(self) -> None:
        assert WeightedBehavior.success_rate == 0.5

    def test_update_returns_status(self) -> None:
        node = WeightedBehavior()
        result = node.update()
        assert result in (Status.SUCCESS, Status.FAILURE)

    def test_update_never_returns_running(self) -> None:
        node = WeightedBehavior()
        results = {node.update() for _ in range(200)}
        assert Status.RUNNING not in results

    def test_probability_distribution(self) -> None:
        """Empirical rate should be within tolerance of success_rate."""

        class HalfRate(WeightedBehavior):
            success_rate = 0.5

        rate = _run_trials(HalfRate)
        assert abs(rate - 0.5) < _TOLERANCE

    def test_seeded_determinism(self) -> None:
        """Same seed → same sequence."""
        random.seed(42)
        node = WeightedBehavior()
        seq_a = [node.update() for _ in range(20)]
        random.seed(42)
        seq_b = [node.update() for _ in range(20)]
        assert seq_a == seq_b


# ---------------------------------------------------------------------------
# SuccessOrRunning
# ---------------------------------------------------------------------------


class TestSuccessOrRunning:
    def test_is_py_trees_behaviour(self) -> None:
        import py_trees

        assert isinstance(SuccessOrRunning(), py_trees.behaviour.Behaviour)

    def test_never_fails(self) -> None:
        node = SuccessOrRunning()
        results = {node.update() for _ in range(500)}
        assert Status.FAILURE not in results

    def test_returns_success_and_running(self) -> None:
        node = SuccessOrRunning()
        results = {node.update() for _ in range(500)}
        assert Status.SUCCESS in results
        assert Status.RUNNING in results

    def test_empirical_distribution(self) -> None:
        """SUCCESS and RUNNING each occur ~50% of the time."""
        node = SuccessOrRunning()
        successes = sum(
            1 for _ in range(_TRIALS) if node.update() == Status.SUCCESS
        )
        rate = successes / _TRIALS
        assert (
            abs(rate - 0.5) < _TOLERANCE
        ), f"SuccessOrRunning: empirical SUCCESS rate={rate:.4f}, expected 0.50"

    def test_default_name(self) -> None:
        assert SuccessOrRunning().name == "SuccessOrRunning"


# ---------------------------------------------------------------------------
# Deterministic extremes
# ---------------------------------------------------------------------------


class TestAlwaysSucceed:
    def test_always_succeeds(self) -> None:
        node = AlwaysSucceed()
        assert all(node.update() == Status.SUCCESS for _ in range(100))

    def test_success_rate_attribute(self) -> None:
        assert AlwaysSucceed.success_rate == 1.0


class TestAlwaysFail:
    def test_always_fails(self) -> None:
        node = AlwaysFail()
        assert all(node.update() == Status.FAILURE for _ in range(100))

    def test_success_rate_attribute(self) -> None:
        assert AlwaysFail.success_rate == 0.0


# ---------------------------------------------------------------------------
# Probability subclasses — success_rate attribute
# ---------------------------------------------------------------------------

_RATE_CASES = [
    (AlmostCertainlySucceed, 93.0 / 100.0),
    (AlmostAlwaysSucceed, 9.0 / 10.0),
    (UsuallySucceed, 3.0 / 4.0),
    (OftenSucceed, 7.0 / 10.0),
    (ProbablySucceed, 2.0 / 3.0),
    (UniformSucceedFail, 1.0 / 2.0),
    (ProbablyFail, 1.0 / 3.0),
    (OftenFail, 3.0 / 10.0),
    (UsuallyFail, 1.0 / 4.0),
    (AlmostAlwaysFail, 1.0 / 10.0),
    (AlmostCertainlyFail, 7.0 / 100.0),
    (OneInTwenty, 1.0 / 20.0),
    (OneInOneHundred, 1.0 / 100.0),
    (OneInTwoHundred, 1.0 / 200.0),
]


@pytest.mark.parametrize("cls,expected_rate", _RATE_CASES)
def test_success_rate_attribute(
    cls: Type[WeightedBehavior], expected_rate: float
) -> None:
    assert abs(cls.success_rate - expected_rate) < 1e-9


@pytest.mark.parametrize("cls,expected_rate", _RATE_CASES)
def test_is_weighted_behavior_subclass(
    cls: Type[WeightedBehavior], expected_rate: float
) -> None:
    assert issubclass(cls, WeightedBehavior)


@pytest.mark.parametrize("cls,expected_rate", _RATE_CASES)
def test_update_returns_valid_status(
    cls: Type[WeightedBehavior], expected_rate: float
) -> None:
    node = cls()
    result = node.update()
    assert result in (Status.SUCCESS, Status.FAILURE)


# ---------------------------------------------------------------------------
# Empirical distribution checks (high-probability nodes only — fast enough)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cls,expected_rate",
    [
        (AlmostCertainlySucceed, 0.93),
        (AlmostAlwaysSucceed, 0.90),
        (UsuallySucceed, 0.75),
        (OftenSucceed, 0.70),
        (UniformSucceedFail, 0.50),
        (OftenFail, 0.30),
        (AlmostAlwaysFail, 0.10),
    ],
)
def test_empirical_distribution(
    cls: Type[WeightedBehavior], expected_rate: float
) -> None:
    rate = _run_trials(cls)
    assert (
        abs(rate - expected_rate) < _TOLERANCE
    ), f"{cls.__name__}: empirical={rate:.4f} expected={expected_rate:.4f}"


# ---------------------------------------------------------------------------
# Aliases
# ---------------------------------------------------------------------------


class TestAliases:
    def test_likely_succeed_is_often_succeed(self) -> None:
        assert LikelySucceed is OftenSucceed

    def test_rarely_succeed_is_almost_always_fail(self) -> None:
        assert RarelySucceed is AlmostAlwaysFail

    def test_likely_fail_is_often_fail(self) -> None:
        assert LikelyFail is OftenFail

    def test_random_succeed_fail_is_uniform(self) -> None:
        assert RandomSucceedFail is UniformSucceedFail

    def test_random_condition_node_is_uniform(self) -> None:
        assert RandomConditionNode is UniformSucceedFail

    def test_random_action_node_is_uniform(self) -> None:
        assert RandomActionNode is UniformSucceedFail


# ---------------------------------------------------------------------------
# Package re-exports (AC-3)
# ---------------------------------------------------------------------------


class TestPackageExports:
    def test_all_names_importable_from_package(self) -> None:
        import vultron.demo.fuzzer as pkg

        expected = [
            "WeightedBehavior",
            "SuccessOrRunning",
            "AlwaysSucceed",
            "AlwaysFail",
            "AlmostCertainlySucceed",
            "AlmostAlwaysSucceed",
            "UsuallySucceed",
            "OftenSucceed",
            "LikelySucceed",
            "ProbablySucceed",
            "UniformSucceedFail",
            "RandomSucceedFail",
            "ProbablyFail",
            "OftenFail",
            "UsuallyFail",
            "AlmostAlwaysFail",
            "RarelySucceed",
            "AlmostCertainlyFail",
            "OneInTwenty",
            "OneInOneHundred",
            "OneInTwoHundred",
            "LikelyFail",
            "RandomConditionNode",
            "RandomActionNode",
        ]
        for name in expected:
            assert hasattr(pkg, name), f"vultron.demo.fuzzer missing: {name}"
