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
"""Unit tests for vultron/demo/fuzzer/report_management/develop_fix.py.

Tests cover:
  - CreateFix is a WeightedBehavior subclass (AC-1)
  - Docstring covers required fields (AC-2)
  - Correct success_rate and status distribution (AC-3)
"""

import py_trees
import pytest
from py_trees.common import Status

from vultron.demo.fuzzer.base import WeightedBehavior
from vultron.demo.fuzzer.call_out_point import ComposerCallOutPoint
from vultron.demo.fuzzer.report_management.develop_fix import CreateFix

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TRIALS = 10_000
_TOLERANCE = 0.03  # ±3 percentage points

_ALL_NODES = [(CreateFix, 9.0 / 10.0)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_trials(node_cls: type, n: int = _TRIALS) -> float:
    """Return empirical success rate over *n* independent ticks."""
    node = node_cls()
    node.setup()
    successes = sum(1 for _ in range(n) if node.update() == Status.SUCCESS)
    return successes / n


# ---------------------------------------------------------------------------
# AC-1: Node uses py_trees base type
# ---------------------------------------------------------------------------


class TestCreateFixIsWeightedBehavior:
    def test_is_weighted_behavior_subclass(self) -> None:
        assert issubclass(CreateFix, WeightedBehavior)

    def test_is_composer_call_out_point(self) -> None:
        assert issubclass(CreateFix, ComposerCallOutPoint)

    def test_output_keys_declared(self) -> None:
        assert "fix_artifact" in CreateFix.output_keys

    def test_output_key_type_is_str(self) -> None:
        assert CreateFix.output_keys["fix_artifact"] is str

    def test_docstring_has_blackboard_contract(self) -> None:
        assert CreateFix.__doc__ and "Blackboard contract" in CreateFix.__doc__

    def test_is_py_trees_behaviour(self) -> None:
        assert isinstance(CreateFix(), py_trees.behaviour.Behaviour)

    def test_default_name_is_class_name(self) -> None:
        assert CreateFix().name == "CreateFix"

    def test_one_node_present(self) -> None:
        assert len(_ALL_NODES) == 1


# ---------------------------------------------------------------------------
# AC-2: Docstring covers required fields per BT-16-003 / BT-16-005
# ---------------------------------------------------------------------------


class TestDocstring:
    def test_has_non_empty_docstring(self) -> None:
        doc = CreateFix.__doc__ or ""
        assert len(doc.strip()) > 0

    @pytest.mark.parametrize(
        "section",
        [
            "semantic function",
            "input category",
            "success probability",
            "automation potential",
        ],
    )
    def test_docstring_has_required_section(self, section: str) -> None:
        doc = (CreateFix.__doc__ or "").lower()
        assert (
            section in doc
        ), f"CreateFix docstring missing '{section}' section"


# ---------------------------------------------------------------------------
# AC-3: success_rate attribute and status distribution
# ---------------------------------------------------------------------------


class TestSuccessRate:
    def test_success_rate_attribute(self) -> None:
        assert abs(CreateFix.success_rate - 9.0 / 10.0) < 1e-9

    def test_update_returns_success_or_failure(self) -> None:
        node = CreateFix()
        node.setup()
        result = node.update()
        assert result in (Status.SUCCESS, Status.FAILURE)

    def test_update_never_returns_running(self) -> None:
        node = CreateFix()
        node.setup()
        results = {node.update() for _ in range(50)}
        assert Status.RUNNING not in results

    def test_empirical_distribution(self) -> None:
        rate = _run_trials(CreateFix)
        expected = 9.0 / 10.0
        assert (
            abs(rate - expected) < _TOLERANCE
        ), f"CreateFix: empirical={rate:.4f} expected={expected:.4f}"
