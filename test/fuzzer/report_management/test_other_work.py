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
"""Unit tests for vultron/demo/fuzzer/report_management/other_work.py.

Tests cover:
  - OtherWork is a WeightedBehavior subclass (AC-1)
  - Docstring covers required fields (AC-2)
  - Correct success_rate and always-success behavior (AC-3)
"""

import py_trees
import pytest
from py_trees.common import Status

from vultron.demo.fuzzer.base import WeightedBehavior
from vultron.demo.fuzzer.report_management.other_work import OtherWork

_ALL_NODES = [(OtherWork, 1.0)]


# ---------------------------------------------------------------------------
# AC-1: Node uses py_trees base type
# ---------------------------------------------------------------------------


class TestOtherWorkIsWeightedBehavior:
    def test_is_weighted_behavior_subclass(self) -> None:
        assert issubclass(OtherWork, WeightedBehavior)

    def test_is_py_trees_behaviour(self) -> None:
        assert isinstance(OtherWork(), py_trees.behaviour.Behaviour)

    def test_default_name_is_class_name(self) -> None:
        assert OtherWork().name == "OtherWork"

    def test_one_node_present(self) -> None:
        assert len(_ALL_NODES) == 1


# ---------------------------------------------------------------------------
# AC-2: Docstring covers required fields per BT-16-003 / BT-16-005
# ---------------------------------------------------------------------------


class TestDocstring:
    def test_has_non_empty_docstring(self) -> None:
        doc = OtherWork.__doc__ or ""
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
        doc = (OtherWork.__doc__ or "").lower()
        assert (
            section in doc
        ), f"OtherWork docstring missing '{section}' section"


# ---------------------------------------------------------------------------
# AC-3: success_rate and deterministic behavior
# ---------------------------------------------------------------------------


class TestSuccessRate:
    def test_success_rate_attribute(self) -> None:
        assert abs(OtherWork.success_rate - 1.0) < 1e-9

    def test_always_succeeds(self) -> None:
        node = OtherWork()
        assert all(node.update() == Status.SUCCESS for _ in range(100))

    def test_update_never_returns_running(self) -> None:
        node = OtherWork()
        results = {node.update() for _ in range(50)}
        assert Status.RUNNING not in results
