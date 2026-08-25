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
"""Tests for the StatusAuthorizationCallOutBundle (issue #1843, ADR-0046).

Covers the two-seam status-authorization call-out bundle:

- Core bundle dataclass + DETERMINISTIC singleton (both seams AlwaysSucceed).
- Demo STOCHASTIC singleton (both seams AlmostAlwaysSucceed, p=0.90).
- Core / demo package re-exports (BT-23-005).
- Both tree builders accept the ``call_out`` bundle in their signature and
  default to the core DETERMINISTIC singleton (RSH-01 / RSH-02 injection seam).
"""

import dataclasses
import inspect

import py_trees
import pytest
from py_trees.common import Status

from vultron.core.behaviors.call_out.bundles.status_authorization import (
    STATUS_AUTHORIZATION_DETERMINISTIC,
    StatusAuthorizationCallOutBundle,
)

# ---------------------------------------------------------------------------
# Core bundle dataclass + DETERMINISTIC singleton
# ---------------------------------------------------------------------------


@pytest.mark.spec("RSH-01-002")
@pytest.mark.spec("RSH-02-001")
def test_bundle_is_frozen_dataclass_with_two_seam_fields():
    """Bundle is a frozen dataclass exposing exactly the two seam factories."""
    assert dataclasses.is_dataclass(StatusAuthorizationCallOutBundle)
    field_names = {
        f.name for f in dataclasses.fields(StatusAuthorizationCallOutBundle)
    }
    assert field_names == {
        "status_adoption_gate_factory",
        "embargo_teardown_authorization_gate_factory",
    }
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


@pytest.mark.spec("RSH-02-002")
def test_deterministic_both_seams_always_succeed():
    """DETERMINISTIC: both seam factories build nodes that tick SUCCESS."""
    for f in dataclasses.fields(STATUS_AUTHORIZATION_DETERMINISTIC):
        factory = getattr(STATUS_AUTHORIZATION_DETERMINISTIC, f.name)
        node = factory("probe")
        assert isinstance(node, py_trees.behaviour.Behaviour)
        node.tick_once()
        assert node.status == Status.SUCCESS


# ---------------------------------------------------------------------------
# Package re-exports (BT-23-005)
# ---------------------------------------------------------------------------


def test_core_bundles_init_re_exports():
    from vultron.core.behaviors.call_out import bundles

    assert hasattr(bundles, "StatusAuthorizationCallOutBundle")
    assert hasattr(bundles, "STATUS_AUTHORIZATION_DETERMINISTIC")


def test_demo_bundles_init_re_exports():
    from vultron.demo.fuzzer import bundles

    assert hasattr(bundles, "StatusAuthorizationCallOutBundle")
    assert hasattr(bundles, "STATUS_AUTHORIZATION_DETERMINISTIC")
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


def test_stochastic_seams_use_probabilistic_backend():
    """STOCHASTIC seams build the p=0.90 AlmostAlwaysSucceed fuzzer node."""
    from vultron.demo.fuzzer.base import AlmostAlwaysSucceed
    from vultron.demo.fuzzer.bundles.status_authorization import (
        STATUS_AUTHORIZATION_STOCHASTIC,
    )

    for f in dataclasses.fields(STATUS_AUTHORIZATION_STOCHASTIC):
        factory = getattr(STATUS_AUTHORIZATION_STOCHASTIC, f.name)
        node = factory("probe")
        assert isinstance(node, AlmostAlwaysSucceed)
        assert node.success_rate == 9.0 / 10.0


# ---------------------------------------------------------------------------
# Tree-builder injection seam (RSH-01 / RSH-02)
# ---------------------------------------------------------------------------


@pytest.mark.spec("RSH-01-002")
def test_add_participant_status_tree_accepts_call_out_bundle():
    from vultron.core.behaviors.status.add_participant_status_tree import (
        add_participant_status_tree,
    )

    sig = inspect.signature(add_participant_status_tree)
    param = sig.parameters["call_out"]
    assert param.default is STATUS_AUTHORIZATION_DETERMINISTIC


@pytest.mark.spec("RSH-02-001")
def test_add_case_status_tree_accepts_call_out_bundle():
    from vultron.core.behaviors.status.add_case_status_tree import (
        add_case_status_tree,
    )

    sig = inspect.signature(add_case_status_tree)
    param = sig.parameters["call_out"]
    assert param.default is STATUS_AUTHORIZATION_DETERMINISTIC
