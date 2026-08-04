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
"""Unit tests for the core-owned call-out seam (ADR-0025, BT-23).

Covers the pieces that moved into ``vultron/core/behaviors/call_out/`` when the
ADR-0025 core→demo inversion was fixed (issue #1793):

- The deterministic ``AlwaysSucceed`` / ``AlwaysFail`` nodes: SUCCESS/FAILURE
  contract, ``success_rate`` parity attributes, py_trees ``Behaviour`` identity,
  and default/custom naming.
- The ``CallOutBackendFactory`` Protocol: the core nodes and the demo
  ``WeightedBehavior`` nodes both satisfy it (the sole substitutability contract
  between the two intentionally-duplicated node families).
- Every ``<DOMAIN>_DETERMINISTIC`` bundle singleton: each factory field builds a
  core deterministic node honouring the Protocol, and no field reaches into the
  ``vultron.demo`` layer.

These lock the contract that core tree builders rely on when they default
``call_out`` to a core DETERMINISTIC bundle.
"""

import py_trees
import pytest
from py_trees.common import Status

from vultron.core.behaviors.call_out import (
    AlwaysFail,
    AlwaysSucceed,
    CallOutBackendFactory,
)
from vultron.core.behaviors.call_out.bundles import (
    ACQUIRE_EXPLOIT_DETERMINISTIC,
    ASSIGN_CVE_ID_DETERMINISTIC,
    ASSIGN_VUL_ID_DETERMINISTIC,
    CLOSE_REPORT_DETERMINISTIC,
    DEPLOY_FIX_DETERMINISTIC,
    DEPLOY_MITIGATION_DETERMINISTIC,
    EMBARGO_DETERMINISTIC,
    PRIORITIZATION_DETERMINISTIC,
    PUBLICATION_DETERMINISTIC,
    REPORT_TO_OTHERS_DETERMINISTIC,
    STATUS_AUTHORIZATION_DETERMINISTIC,
    VALIDATION_DETERMINISTIC,
)

# All pre-built core DETERMINISTIC bundle singletons.
_DETERMINISTIC_BUNDLES = [
    ACQUIRE_EXPLOIT_DETERMINISTIC,
    ASSIGN_CVE_ID_DETERMINISTIC,
    ASSIGN_VUL_ID_DETERMINISTIC,
    CLOSE_REPORT_DETERMINISTIC,
    DEPLOY_FIX_DETERMINISTIC,
    DEPLOY_MITIGATION_DETERMINISTIC,
    EMBARGO_DETERMINISTIC,
    PRIORITIZATION_DETERMINISTIC,
    PUBLICATION_DETERMINISTIC,
    REPORT_TO_OTHERS_DETERMINISTIC,
    STATUS_AUTHORIZATION_DETERMINISTIC,
    VALIDATION_DETERMINISTIC,
]


def _factory_fields(bundle) -> list:
    """Return every CallOutBackendFactory field value on a frozen bundle."""
    return [getattr(bundle, f) for f in vars(bundle)]


# ---------------------------------------------------------------------------
# AlwaysSucceed / AlwaysFail contract
# ---------------------------------------------------------------------------


class TestAlwaysSucceed:
    def test_update_returns_success(self):
        node = AlwaysSucceed("EvaluateReportCredibility")
        assert all(node.update() == Status.SUCCESS for _ in range(50))

    def test_tick_sets_success_status(self):
        node = AlwaysSucceed("n")
        node.tick_once()
        assert node.status == Status.SUCCESS

    def test_success_rate_attribute(self):
        assert AlwaysSucceed.success_rate == 1.0

    def test_is_py_trees_behaviour(self):
        assert isinstance(AlwaysSucceed("n"), py_trees.behaviour.Behaviour)

    def test_name_passthrough(self):
        assert AlwaysSucceed("MyNode").name == "MyNode"

    def test_default_name_is_class_name(self):
        assert AlwaysSucceed().name == "AlwaysSucceed"


class TestAlwaysFail:
    def test_update_returns_failure(self):
        node = AlwaysFail("DeployFix")
        assert all(node.update() == Status.FAILURE for _ in range(50))

    def test_tick_sets_failure_status(self):
        node = AlwaysFail("n")
        node.tick_once()
        assert node.status == Status.FAILURE

    def test_success_rate_attribute(self):
        assert AlwaysFail.success_rate == 0.0

    def test_is_py_trees_behaviour(self):
        assert isinstance(AlwaysFail("n"), py_trees.behaviour.Behaviour)

    def test_name_passthrough(self):
        assert AlwaysFail("MyNode").name == "MyNode"

    def test_default_name_is_class_name(self):
        assert AlwaysFail().name == "AlwaysFail"


def test_core_nodes_do_not_subclass_weighted_behavior():
    """Core nodes are deterministic — not the demo WeightedBehavior family.

    They are intentionally duplicated from (not cross-imported with) the demo
    ``AlwaysSucceed``/``AlwaysFail`` so that core never imports ``vultron.demo``.
    """
    assert AlwaysSucceed.__module__ == "vultron.core.behaviors.call_out.nodes"
    assert AlwaysFail.__module__ == "vultron.core.behaviors.call_out.nodes"


# ---------------------------------------------------------------------------
# CallOutBackendFactory Protocol conformance
# ---------------------------------------------------------------------------


def test_core_nodes_satisfy_backend_factory_protocol():
    """Both core node classes are valid CallOutBackendFactory callables."""
    assert isinstance(AlwaysSucceed, CallOutBackendFactory)
    assert isinstance(AlwaysFail, CallOutBackendFactory)


def test_demo_and_core_nodes_share_the_factory_contract():
    """The demo WeightedBehavior node also satisfies the same Protocol.

    This is the sole substitutability contract between the two duplicated
    families — verifying it here guards the design decision from #1793.
    """
    from vultron.demo.fuzzer.base import AlwaysSucceed as DemoAlwaysSucceed

    assert isinstance(DemoAlwaysSucceed, CallOutBackendFactory)
    # Distinct classes, same contract.
    assert DemoAlwaysSucceed is not AlwaysSucceed


# ---------------------------------------------------------------------------
# DETERMINISTIC bundle singletons
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bundle", _DETERMINISTIC_BUNDLES)
def test_bundle_factories_build_core_deterministic_nodes(bundle):
    """Every field of each DETERMINISTIC bundle builds a core AlwaysSucceed/Fail
    node that honours the CallOutBackendFactory contract."""
    fields = _factory_fields(bundle)
    assert fields, f"{type(bundle).__name__} has no factory fields"
    for factory in fields:
        assert isinstance(factory, CallOutBackendFactory)
        node = factory("probe")
        assert isinstance(node, (AlwaysSucceed, AlwaysFail))
        assert node.name == "probe"


@pytest.mark.parametrize("bundle", _DETERMINISTIC_BUNDLES)
def test_bundle_nodes_are_deterministic_on_tick(bundle):
    """Each bundle node ticks to a fixed SUCCESS or FAILURE (never RUNNING)."""
    for factory in _factory_fields(bundle):
        node = factory("probe")
        node.tick_once()
        assert node.status in (Status.SUCCESS, Status.FAILURE)


def test_bundles_are_frozen():
    """Bundles are frozen dataclasses — fields cannot be reassigned."""
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        VALIDATION_DETERMINISTIC.credibility_factory = (  # type: ignore[misc]
            lambda n: AlwaysFail(n)
        )
