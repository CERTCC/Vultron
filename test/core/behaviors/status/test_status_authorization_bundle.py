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
"""Tests for the StatusAuthorizationCallOutBundle (issue #1843, ADR-0046, ADR-0076).

Covers the status-authorization call-out bundle, whose one field is the
adoption gate; adoption also authorizes the embargo teardown (ADR-0166):

- Core bundle dataclass + DETERMINISTIC singleton (RequireCaseOwnerApprovalNode).
- Core PERMISSIVE singleton (AlwaysSucceed — explicit override only).
- Demo STOCHASTIC singleton (AlmostAlwaysSucceed, p=0.90).
- Core / demo package re-exports (BT-23-005).
- The tree builder accepts the ``call_out`` bundle in its signature and
  defaults to the core DETERMINISTIC singleton (RSH-01 injection seam), and
  runs the teardown with no second gate (RSH-01-004).
"""

import dataclasses
import inspect

import py_trees
import pytest
from py_trees.common import Status

from vultron.core.behaviors.call_out import unwrap_call_out
from vultron.core.behaviors.call_out.bundles.status_authorization import (
    STATUS_AUTHORIZATION_DETERMINISTIC,
    STATUS_AUTHORIZATION_PERMISSIVE,
    StatusAuthorizationCallOutBundle,
)

# ---------------------------------------------------------------------------
# Core bundle dataclass + DETERMINISTIC singleton
# ---------------------------------------------------------------------------


@pytest.mark.spec("RSH-01-002")
def test_bundle_is_frozen_dataclass_with_only_the_adoption_gate():
    """Bundle is a frozen dataclass exposing only the adoption gate factory.

    Adoption also authorizes the embargo teardown, so the bundle has no
    teardown gate (ADR-0166).
    """
    assert dataclasses.is_dataclass(StatusAuthorizationCallOutBundle)
    field_names = {
        f.name for f in dataclasses.fields(StatusAuthorizationCallOutBundle)
    }
    assert field_names == {"status_adoption_gate_factory"}
    # frozen=True → mutating a field raises FrozenInstanceError.
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        STATUS_AUTHORIZATION_DETERMINISTIC.status_adoption_gate_factory = None  # type: ignore[misc]


def test_deterministic_is_instance_of_bundle():
    assert isinstance(
        STATUS_AUTHORIZATION_DETERMINISTIC, StatusAuthorizationCallOutBundle
    )


def test_deterministic_fields_satisfy_protocol():
    """Each DETERMINISTIC field default satisfies CallOutBackendFactory."""
    from vultron.core.behaviors.call_out.protocol import CallOutBackendFactory

    for f in dataclasses.fields(STATUS_AUTHORIZATION_DETERMINISTIC):
        val = getattr(STATUS_AUTHORIZATION_DETERMINISTIC, f.name)
        assert isinstance(val, CallOutBackendFactory)


@pytest.mark.spec("RSH-07-001")
def test_deterministic_adoption_gate_requires_case_owner_approval():
    """DETERMINISTIC: the adoption gate builds a RequireCaseOwnerApprovalNode that ticks FAILURE."""
    from vultron.core.behaviors.call_out.nodes import (
        RequireCaseOwnerApprovalNode,
    )

    for f in dataclasses.fields(STATUS_AUTHORIZATION_DETERMINISTIC):
        factory = getattr(STATUS_AUTHORIZATION_DETERMINISTIC, f.name)
        node = factory("probe")
        assert isinstance(unwrap_call_out(node), RequireCaseOwnerApprovalNode)
        node.tick_once()
        assert node.status == Status.FAILURE


@pytest.mark.spec("RSH-07-003")
def test_permissive_adoption_gate_always_succeeds():
    """PERMISSIVE: the adoption gate builds a node that ticks SUCCESS (explicit override)."""
    for f in dataclasses.fields(STATUS_AUTHORIZATION_PERMISSIVE):
        factory = getattr(STATUS_AUTHORIZATION_PERMISSIVE, f.name)
        node = factory("probe")
        assert isinstance(node, py_trees.behaviour.Behaviour)
        node.tick_once()
        assert node.status == Status.SUCCESS


def test_permissive_is_instance_of_bundle():
    assert isinstance(
        STATUS_AUTHORIZATION_PERMISSIVE, StatusAuthorizationCallOutBundle
    )


def test_require_case_owner_approval_node_returns_failure():
    """RequireCaseOwnerApprovalNode always returns FAILURE (ADR-0076)."""
    from vultron.core.behaviors.call_out.nodes import (
        RequireCaseOwnerApprovalNode,
    )

    node = RequireCaseOwnerApprovalNode("probe")
    node.tick_once()
    assert node.status == Status.FAILURE


# ---------------------------------------------------------------------------
# Package re-exports (BT-23-005)
# ---------------------------------------------------------------------------


def test_core_bundles_init_re_exports():
    from vultron.core.behaviors.call_out import bundles

    assert hasattr(bundles, "StatusAuthorizationCallOutBundle")
    assert hasattr(bundles, "STATUS_AUTHORIZATION_DETERMINISTIC")
    assert hasattr(bundles, "STATUS_AUTHORIZATION_PERMISSIVE")


def test_demo_bundles_init_re_exports():
    from vultron.demo.fuzzer import bundles

    assert hasattr(bundles, "StatusAuthorizationCallOutBundle")
    assert hasattr(bundles, "STATUS_AUTHORIZATION_DETERMINISTIC")
    assert hasattr(bundles, "STATUS_AUTHORIZATION_PERMISSIVE")
    assert hasattr(bundles, "STATUS_AUTHORIZATION_STOCHASTIC")


# ---------------------------------------------------------------------------
# Demo STOCHASTIC singleton
# ---------------------------------------------------------------------------


def test_stochastic_is_instance_of_bundle():
    from vultron.demo.fuzzer.bundles.status_authorization import (
        STATUS_AUTHORIZATION_STOCHASTIC,
    )

    assert isinstance(
        STATUS_AUTHORIZATION_STOCHASTIC, StatusAuthorizationCallOutBundle
    )


def test_stochastic_adoption_gate_uses_probabilistic_backend():
    """The STOCHASTIC adoption gate builds the p=0.90 AlmostAlwaysSucceed fuzzer node."""
    from vultron.demo.fuzzer.base import AlmostAlwaysSucceed
    from vultron.demo.fuzzer.bundles.status_authorization import (
        STATUS_AUTHORIZATION_STOCHASTIC,
    )

    for f in dataclasses.fields(STATUS_AUTHORIZATION_STOCHASTIC):
        factory = getattr(STATUS_AUTHORIZATION_STOCHASTIC, f.name)
        node = factory("probe")
        inner = unwrap_call_out(node)
        assert isinstance(inner, AlmostAlwaysSucceed)
        assert inner.success_rate == 9.0 / 10.0


# ---------------------------------------------------------------------------
# Tree-builder injection seam (RSH-01)
# ---------------------------------------------------------------------------


@pytest.mark.spec("RSH-01-002")
def test_add_participant_status_tree_accepts_call_out_bundle():
    from vultron.core.behaviors.status.add_participant_status_tree import (
        add_participant_status_tree,
    )

    sig = inspect.signature(add_participant_status_tree)
    param = sig.parameters["call_out"]
    assert param.default is STATUS_AUTHORIZATION_DETERMINISTIC


@pytest.mark.spec("RSH-01-004")
def test_teardown_follows_the_canonical_write_with_no_second_gate(
    make_payload,
):
    """ThreatTerminationBranchNode runs directly after the post-adoption
    CaseStatus write, with no teardown authorization call-out between them
    (RSH-01-004, ADR-0166)."""
    from vultron.core.behaviors.status.add_participant_status_tree import (
        add_participant_status_tree,
    )
    from vultron.core.use_cases.received.status import (
        AddParticipantStatusToParticipantReceivedUseCase,
    )
    from vultron.wire.as2.factories import add_status_to_participant_activity
    from vultron.wire.as2.vocab.objects.case_participant import (
        as_CaseParticipant,
    )
    from vultron.wire.as2.vocab.objects.case_status import as_ParticipantStatus

    case_id = "https://example.org/cases/rsh-01-004"
    actor_id = "https://example.org/actors/vendor"
    activity = add_status_to_participant_activity(
        status=as_ParticipantStatus(context=case_id),
        target=as_CaseParticipant(
            id_=f"{case_id}/participants/vendor",
            context=case_id,
            attributed_to=actor_id,
        ),
        actor=actor_id,
    )
    tree = add_participant_status_tree(
        request=make_payload(activity),
        case_id=case_id,
        sender_rule=(
            AddParticipantStatusToParticipantReceivedUseCase.sender_entitlement
        ),
    )

    names = [node.name for node in tree.iterate()]
    assert "EmbargoTeardownAuthorizationGate" not in names
    adopt = next(node for node in tree.iterate() if node.name == "AdoptStatus")
    children = [child.name for child in adopt.children]
    # The teardown sits directly after the emit, inside only the
    # FailureIsSuccess wrapper that keeps the act when the teardown fails.
    teardown_or_skip = adopt.children[
        children.index("EmitCaseStatusUpdate") + 1
    ]
    assert teardown_or_skip.name == "TeardownOrSkip"
    assert [child.name for child in teardown_or_skip.children] == [
        "ThreatTerminationBranch"
    ]


@pytest.mark.spec("RSH-04-005")
def test_add_case_status_tree_takes_no_call_out_bundle():
    """A received Add(CaseStatus) gates nothing, so its tree has no
    authorization seam (RSH-04-005)."""
    from vultron.core.behaviors.status.add_case_status_tree import (
        add_case_status_tree,
    )

    assert "call_out" not in inspect.signature(add_case_status_tree).parameters
