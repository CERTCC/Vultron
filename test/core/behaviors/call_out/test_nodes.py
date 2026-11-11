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

- The deterministic ``AlwaysSucceed`` / ``AlwaysFail`` nodes: *yes* / *no*
  answers (ADR-0183), ``success_rate`` parity attributes, py_trees ``Behaviour`` identity,
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

from test.support.call_out import bind_test_target, tick_call_out
from vultron.core.behaviors.call_out import (
    AlwaysFail,
    AlwaysSucceed,
    CallOutBackendFactory,
    unwrap_call_out,
)
from vultron.core.behaviors.call_out.answer import CallOutAnswer
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
    STATUS_AUTHORIZATION_DETERMINISTIC,
    VALIDATION_DETERMINISTIC,
)
from vultron.core.behaviors.call_out.bundles.assign_cve_id import (
    DeterministicEvaluateCveEligibility,
)
from vultron.core.behaviors.call_out.nodes import (
    CASE_OWNER_APPROVAL_REQUIRED_REASON,
    DETERMINISTIC_REFUSAL_REASON,
    RequireCaseOwnerApprovalNode,
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
        assert all(tick_call_out(node) == Status.SUCCESS for _ in range(50))

    def test_tick_sets_success_status(self):
        node = AlwaysSucceed("n")
        assert tick_call_out(node) == Status.SUCCESS
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
        assert all(tick_call_out(node) == Status.FAILURE for _ in range(50))

    def test_tick_sets_failure_status(self):
        node = AlwaysFail("n")
        assert tick_call_out(node) == Status.FAILURE
        assert node.status == Status.FAILURE

    def test_success_rate_attribute(self):
        assert AlwaysFail.success_rate == 0.0

    def test_is_py_trees_behaviour(self):
        assert isinstance(AlwaysFail("n"), py_trees.behaviour.Behaviour)

    def test_name_passthrough(self):
        assert AlwaysFail("MyNode").name == "MyNode"

    def test_default_name_is_class_name(self):
        assert AlwaysFail().name == "AlwaysFail"


class TestRequireCaseOwnerApprovalNode:
    def test_update_returns_failure(self):
        node = RequireCaseOwnerApprovalNode("CaseOwnerApprovesStatusUpdate")
        assert all(tick_call_out(node) == Status.FAILURE for _ in range(50))

    def test_tick_sets_failure_status(self):
        node = RequireCaseOwnerApprovalNode("n")
        assert tick_call_out(node) == Status.FAILURE
        assert node.status == Status.FAILURE

    def test_success_rate_attribute(self):
        assert RequireCaseOwnerApprovalNode.success_rate == 0.0

    def test_is_py_trees_behaviour(self):
        assert isinstance(
            RequireCaseOwnerApprovalNode("n"), py_trees.behaviour.Behaviour
        )

    def test_name_passthrough(self):
        assert RequireCaseOwnerApprovalNode("MyNode").name == "MyNode"

    def test_default_name_is_class_name(self):
        assert (
            RequireCaseOwnerApprovalNode().name
            == "RequireCaseOwnerApprovalNode"
        )


@pytest.mark.spec("BT-18-007")
def test_deterministic_refusals_carry_a_reason():
    """AlwaysFail and the approval gate answer no, each with its reason."""
    assert AlwaysFail("n").answer() == CallOutAnswer.no(
        DETERMINISTIC_REFUSAL_REASON
    )
    assert RequireCaseOwnerApprovalNode("n").answer() == CallOutAnswer.no(
        CASE_OWNER_APPROVAL_REQUIRED_REASON
    )


def test_always_succeed_answers_yes_with_no_outputs():
    assert AlwaysSucceed("n").answer() == CallOutAnswer.yes()


def test_core_nodes_do_not_subclass_weighted_behavior():
    """Core nodes are deterministic — not the demo WeightedBehavior family.

    They are intentionally duplicated from (not cross-imported with) the demo
    ``AlwaysSucceed``/``AlwaysFail`` so that core never imports ``vultron.demo``.
    """
    assert AlwaysSucceed.__module__ == "vultron.core.behaviors.call_out.nodes"
    assert AlwaysFail.__module__ == "vultron.core.behaviors.call_out.nodes"
    assert (
        RequireCaseOwnerApprovalNode.__module__
        == "vultron.core.behaviors.call_out.nodes"
    )


# ---------------------------------------------------------------------------
# CallOutBackendFactory Protocol conformance
# ---------------------------------------------------------------------------


def test_core_nodes_satisfy_backend_factory_protocol():
    """All core node classes are valid CallOutBackendFactory callables."""
    assert isinstance(AlwaysSucceed, CallOutBackendFactory)
    assert isinstance(AlwaysFail, CallOutBackendFactory)
    assert isinstance(RequireCaseOwnerApprovalNode, CallOutBackendFactory)


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


_CORE_DETERMINISTIC_NODE_TYPES = (
    AlwaysSucceed,
    AlwaysFail,
    RequireCaseOwnerApprovalNode,
    DeterministicEvaluateCveEligibility,
)


@pytest.mark.parametrize("bundle", _DETERMINISTIC_BUNDLES)
def test_bundle_factories_build_core_deterministic_nodes(bundle):
    """Every field of each DETERMINISTIC bundle builds a core deterministic node
    that honours the CallOutBackendFactory contract.

    Accepted types: AlwaysSucceed, AlwaysFail, RequireCaseOwnerApprovalNode
    (security-significant gates default to RequireCaseOwnerApprovalNode per
    ADR-0076), or the hand-built eligibility default (BT-23-013); a default
    bound to a capability by ``always_succeed_as`` or ``always_fail_as`` is
    an ``AlwaysSucceed`` or ``AlwaysFail``.
    """
    fields = _factory_fields(bundle)
    assert fields, f"{type(bundle).__name__} has no factory fields"
    for factory in fields:
        assert isinstance(factory, CallOutBackendFactory)
        node = factory("probe")
        assert isinstance(
            unwrap_call_out(node), _CORE_DETERMINISTIC_NODE_TYPES
        )
        assert node.name == "probe"


@pytest.mark.parametrize("bundle", _DETERMINISTIC_BUNDLES)
def test_bundle_nodes_are_deterministic_on_tick(bundle):
    """Each bundle node ticks to a fixed SUCCESS or FAILURE (never RUNNING)."""
    for factory in _factory_fields(bundle):
        node = bind_test_target(factory("probe"))
        node.tick_once()
        assert node.status in (Status.SUCCESS, Status.FAILURE)


def test_bundles_are_frozen():
    """Bundles are frozen dataclasses — fields cannot be reassigned."""
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        VALIDATION_DETERMINISTIC.credibility_factory = (  # type: ignore[misc]
            AlwaysFail
        )


# ---------------------------------------------------------------------------
# Defaults bound to a capability declaration (BT-23-013)
# ---------------------------------------------------------------------------


def test_yes_value_is_true_for_bool_and_the_empty_value_otherwise():
    from vultron.core.behaviors.call_out.answer import yes_value
    from vultron.core.behaviors.report.publication_intent import (
        PublicationIntentDecision,
    )

    assert yes_value(bool) is True
    assert yes_value(str) == ""
    assert yes_value(list) == []
    assert yes_value(PublicationIntentDecision) == PublicationIntentDecision()


def test_yes_value_refuses_a_type_it_cannot_build():
    from pydantic import BaseModel

    from vultron.core.behaviors.call_out.answer import yes_value

    class _Needs(BaseModel):
        value: str

    with pytest.raises(TypeError, match="cannot build a _Needs"):
        yes_value(_Needs)


@pytest.mark.spec("BT-23-013")
def test_always_succeed_as_writes_every_declared_output():
    from vultron.core.behaviors.call_out.capabilities.report_management.assign_vul_id.eligibility import (
        ProductInCNAScopeCapability,
    )
    from vultron.core.behaviors.call_out.nodes import always_succeed_as

    bound = always_succeed_as(ProductInCNAScopeCapability)
    assert issubclass(bound, AlwaysSucceed)
    assert bound.declaration() is ProductInCNAScopeCapability  # type: ignore[attr-defined]
    py_trees.blackboard.Blackboard.storage.clear()
    assert tick_call_out(bound("n")) == Status.SUCCESS
    storage = py_trees.blackboard.Blackboard.storage
    assert storage["/product_in_cna_scope"] is True
    assert storage["/product_in_cna_scope_rationale"] == ""
    py_trees.blackboard.Blackboard.storage.clear()


def test_a_binding_is_built_once_per_capability():
    from vultron.core.behaviors.call_out.capabilities.report_management.develop_fix import (
        CreateFixCapability,
    )
    from vultron.core.behaviors.call_out.nodes import (
        always_fail_as,
        always_succeed_as,
    )

    assert always_succeed_as(CreateFixCapability) is always_succeed_as(
        CreateFixCapability
    )
    assert always_fail_as(CreateFixCapability) is not always_succeed_as(
        CreateFixCapability
    )


def test_an_actuator_binds_as_a_no_op_actuator():
    from vultron.core.behaviors.call_out.capabilities.report_management.publication.intents import (
        PublishCapability,
    )
    from vultron.core.behaviors.call_out.nodes import (
        NoOpActuator,
        always_succeed_as,
    )

    bound = always_succeed_as(PublishCapability)
    assert issubclass(bound, NoOpActuator)
    assert tick_call_out(bound("n")) == Status.SUCCESS


@pytest.mark.spec("BT-18-002")
def test_always_fail_as_answers_as_always_fail():
    from vultron.core.behaviors.call_out.capabilities.report_management.develop_fix import (
        CreateFixCapability,
    )
    from vultron.core.behaviors.call_out.nodes import always_fail_as

    bound = always_fail_as(CreateFixCapability)
    assert issubclass(bound, AlwaysFail)
    assert bound("n").answer() == AlwaysFail("n").answer()
    py_trees.blackboard.Blackboard.storage.clear()
    assert tick_call_out(bound("n")) == Status.FAILURE
    assert "/fix_artifact" not in py_trees.blackboard.Blackboard.storage
    py_trees.blackboard.Blackboard.storage.clear()


def test_a_binding_refuses_what_is_not_a_declaration():
    from vultron.core.behaviors.call_out.capability import EvaluatorCapability
    from vultron.core.behaviors.call_out.nodes import always_succeed_as

    with pytest.raises(TypeError, match="not a capability declaration"):
        always_succeed_as(EvaluatorCapability)
    with pytest.raises(TypeError, match="not a capability declaration"):
        always_succeed_as(AlwaysSucceed)  # type: ignore[arg-type]


def test_a_binding_refuses_an_output_no_constant_can_fill():
    from py_trees.ports import PortInformation
    from pydantic import BaseModel

    from vultron.core.behaviors.call_out.capability import EvaluatorCapability
    from vultron.core.behaviors.call_out.nodes import always_succeed_as

    class _Needs(BaseModel):
        value: str

    class _NeedsCapability(EvaluatorCapability):
        OUTPUT_PORTS = {"needs": PortInformation(data_type=_Needs)}

    with pytest.raises(TypeError, match="cannot build a _Needs"):
        always_succeed_as(_NeedsCapability)


def test_a_floor_binding_refuses_a_capability_with_refusal_ports():
    from py_trees.ports import PortInformation

    from vultron.core.behaviors.call_out.capability import EvaluatorCapability
    from vultron.core.behaviors.call_out.nodes import always_fail_as

    class _RefusesCapability(EvaluatorCapability):
        REFUSAL_PORTS = {"why": PortInformation(data_type=str)}

    with pytest.raises(TypeError, match="declares refusal ports"):
        always_fail_as(_RefusesCapability)


def test_an_actuator_floor_binding_answers_no_once_bound():
    from vultron.core.behaviors.call_out.capabilities.report_management.publication.intents import (
        PublishCapability,
    )
    from vultron.core.behaviors.call_out.nodes import always_fail_as

    bound = always_fail_as(PublishCapability)
    assert issubclass(bound, AlwaysFail)
    # tick_call_out binds the one target an Actuator acts on (BT-18-041).
    assert tick_call_out(bound("n")) == Status.FAILURE
