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
"""Bundle-level tests for all call-out backend domain bundles (BT-23-003).

Verifies:
- BT-23-004: CallOutBackendFactory is a runtime-checkable Protocol; each
  bundle field satisfies isinstance checks at runtime.
- BT-23-003: Bundle classes are frozen @dataclasses with the expected fields.
- BT-23-001: DETERMINISTIC and STOCHASTIC singletons are exported from each
  bundle module and from the top-level bundles/__init__.py.
- Singletons are immutable (FrozenInstanceError on mutation attempt).
- All bundle classes and singletons are re-exported from the top-level
  vultron.demo.fuzzer.bundles package.
"""

import dataclasses

import pytest

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _assert_frozen(instance):
    """Assert that frozen=True prevents field mutation."""
    fields = dataclasses.fields(instance)
    if not fields:
        return
    first = fields[0].name
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        setattr(instance, first, None)


# ---------------------------------------------------------------------------
# Protocol conformance (BT-23-004)
# ---------------------------------------------------------------------------


def test_call_out_backend_factory_protocol_is_runtime_checkable():
    """CallOutBackendFactory is @runtime_checkable — isinstance() usable at runtime."""
    from vultron.core.behaviors.call_out_point import CallOutBackendFactory
    from vultron.demo.fuzzer.base import AlwaysSucceed

    def _factory(name):
        return AlwaysSucceed(name)

    assert isinstance(_factory, CallOutBackendFactory)


def test_bundle_fields_satisfy_protocol():
    """Each field default of DETERMINISTIC satisfies the CallOutBackendFactory Protocol."""
    from vultron.core.behaviors.call_out_point import CallOutBackendFactory
    from vultron.demo.fuzzer.bundles.validation import VALIDATION_DETERMINISTIC

    for f in dataclasses.fields(VALIDATION_DETERMINISTIC):
        val = getattr(VALIDATION_DETERMINISTIC, f.name)
        assert isinstance(
            val, CallOutBackendFactory
        ), f"Field {f.name!r} default does not satisfy CallOutBackendFactory: {val!r}"


# ---------------------------------------------------------------------------
# Frozen dataclass invariants (BT-23-003)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "module_path,class_name",
    [
        ("vultron.demo.fuzzer.bundles.validation", "ValidationCallOutBundle"),
        (
            "vultron.demo.fuzzer.bundles.prioritization",
            "PrioritizationCallOutBundle",
        ),
        ("vultron.demo.fuzzer.bundles.embargo", "EmbargoCallOutBundle"),
        (
            "vultron.demo.fuzzer.bundles.publication",
            "PublicationCallOutBundle",
        ),
        (
            "vultron.demo.fuzzer.bundles.report_to_others",
            "ReportToOthersCallOutBundle",
        ),
        ("vultron.demo.fuzzer.bundles.deploy_fix", "DeployFixCallOutBundle"),
        (
            "vultron.demo.fuzzer.bundles.acquire_exploit",
            "AcquireExploitCallOutBundle",
        ),
        (
            "vultron.demo.fuzzer.bundles.assign_vul_id",
            "AssignVulIdCallOutBundle",
        ),
        (
            "vultron.demo.fuzzer.bundles.close_report",
            "CloseReportCallOutBundle",
        ),
    ],
)
def test_bundle_is_frozen_dataclass(module_path, class_name):
    """Each bundle class is a frozen dataclass (mutation must raise FrozenInstanceError)."""
    import importlib

    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name)
    assert dataclasses.is_dataclass(cls), f"{class_name} must be a dataclass"
    params = dataclasses.fields(cls)
    # Frozen = attempting mutation on an instance raises FrozenInstanceError.
    instance = cls()
    _assert_frozen(instance)
    # All fields must be CallOutBackendFactory-typed
    from vultron.core.behaviors.call_out_point import CallOutBackendFactory

    for f in params:
        val = getattr(instance, f.name)
        assert isinstance(
            val, CallOutBackendFactory
        ), f"{class_name}.{f.name} default does not satisfy CallOutBackendFactory: {val!r}"


# ---------------------------------------------------------------------------
# Singleton immutability (BT-23-003)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "module_path,det_name,sto_name",
    [
        (
            "vultron.demo.fuzzer.bundles.validation",
            "VALIDATION_DETERMINISTIC",
            "VALIDATION_STOCHASTIC",
        ),
        (
            "vultron.demo.fuzzer.bundles.prioritization",
            "PRIORITIZATION_DETERMINISTIC",
            "PRIORITIZATION_STOCHASTIC",
        ),
        (
            "vultron.demo.fuzzer.bundles.embargo",
            "EMBARGO_DETERMINISTIC",
            "EMBARGO_STOCHASTIC",
        ),
        (
            "vultron.demo.fuzzer.bundles.publication",
            "PUBLICATION_DETERMINISTIC",
            "PUBLICATION_STOCHASTIC",
        ),
        (
            "vultron.demo.fuzzer.bundles.report_to_others",
            "REPORT_TO_OTHERS_DETERMINISTIC",
            "REPORT_TO_OTHERS_STOCHASTIC",
        ),
        (
            "vultron.demo.fuzzer.bundles.deploy_fix",
            "DEPLOY_FIX_DETERMINISTIC",
            "DEPLOY_FIX_STOCHASTIC",
        ),
        (
            "vultron.demo.fuzzer.bundles.acquire_exploit",
            "ACQUIRE_EXPLOIT_DETERMINISTIC",
            "ACQUIRE_EXPLOIT_STOCHASTIC",
        ),
        (
            "vultron.demo.fuzzer.bundles.assign_vul_id",
            "ASSIGN_VUL_ID_DETERMINISTIC",
            "ASSIGN_VUL_ID_STOCHASTIC",
        ),
        (
            "vultron.demo.fuzzer.bundles.close_report",
            "CLOSE_REPORT_DETERMINISTIC",
            "CLOSE_REPORT_STOCHASTIC",
        ),
    ],
)
def test_singletons_are_immutable(module_path, det_name, sto_name):
    """DETERMINISTIC and STOCHASTIC singletons are immutable."""
    import importlib

    mod = importlib.import_module(module_path)
    det = getattr(mod, det_name)
    sto = getattr(mod, sto_name)
    _assert_frozen(det)
    _assert_frozen(sto)


# ---------------------------------------------------------------------------
# Top-level __init__ re-exports (BT-23-005)
# ---------------------------------------------------------------------------


def test_bundles_init_re_exports_all_classes_and_singletons():
    """vultron.demo.fuzzer.bundles re-exports all 9 bundle classes and 18 singletons."""
    import vultron.demo.fuzzer.bundles as bundles_pkg

    expected_classes = [
        "ValidationCallOutBundle",
        "PrioritizationCallOutBundle",
        "EmbargoCallOutBundle",
        "PublicationCallOutBundle",
        "ReportToOthersCallOutBundle",
        "DeployFixCallOutBundle",
        "AcquireExploitCallOutBundle",
        "AssignVulIdCallOutBundle",
        "CloseReportCallOutBundle",
    ]
    expected_singletons = [
        "VALIDATION_DETERMINISTIC",
        "VALIDATION_STOCHASTIC",
        "PRIORITIZATION_DETERMINISTIC",
        "PRIORITIZATION_STOCHASTIC",
        "EMBARGO_DETERMINISTIC",
        "EMBARGO_STOCHASTIC",
        "PUBLICATION_DETERMINISTIC",
        "PUBLICATION_STOCHASTIC",
        "REPORT_TO_OTHERS_DETERMINISTIC",
        "REPORT_TO_OTHERS_STOCHASTIC",
        "DEPLOY_FIX_DETERMINISTIC",
        "DEPLOY_FIX_STOCHASTIC",
        "ACQUIRE_EXPLOIT_DETERMINISTIC",
        "ACQUIRE_EXPLOIT_STOCHASTIC",
        "ASSIGN_VUL_ID_DETERMINISTIC",
        "ASSIGN_VUL_ID_STOCHASTIC",
        "CLOSE_REPORT_DETERMINISTIC",
        "CLOSE_REPORT_STOCHASTIC",
    ]
    for name in expected_classes + expected_singletons:
        assert hasattr(
            bundles_pkg, name
        ), f"vultron.demo.fuzzer.bundles does not export {name!r}"
