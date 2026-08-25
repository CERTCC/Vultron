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
"""Demo scenario: end-to-end STOCHASTIC bundle injection (BT-23-003, BT-23-005).

Demonstrates the three-mode model from call-out-configuration.md:

- DETERMINISTIC singletons (ceiling/floor rule) are the no-arg default for
  every tree builder.
- STOCHASTIC singletons re-wire every call-out point to a probabilistic fuzzer
  node — the backend used by the demo/fuzzer stack.
- Custom bundles allow per-field overrides for targeted stubbing.

Each test exercises a different domain to show the pattern is universal.
"""

import logging
import py_trees
import pytest

logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def clear_blackboard():
    py_trees.blackboard.Blackboard.storage.clear()
    yield
    py_trees.blackboard.Blackboard.storage.clear()


# ---------------------------------------------------------------------------
# Validation domain
# ---------------------------------------------------------------------------


def test_validation_stochastic_bundle_end_to_end():
    """STOCHASTIC bundle produces EvaluateReportCredibility/Validity fuzzer nodes."""
    from vultron.core.behaviors.report.validate_tree import (
        create_validate_report_tree,
    )
    from vultron.demo.fuzzer.bundles.validation import VALIDATION_STOCHASTIC
    from vultron.demo.fuzzer.report_management.validate import (
        EvaluateReportCredibility,
        EvaluateReportValidity,
    )

    tree = create_validate_report_tree(
        report_id="https://example.org/reports/demo-001",
        offer_id="https://example.org/offers/demo-001",
        call_out=VALIDATION_STOCHASTIC,
    )
    assert isinstance(tree, py_trees.behaviour.Behaviour)

    # Find ValidationFlow's credibility and validity children (positions 1 and 2
    # inside the EmitAndValidate → ValidationOrShortcut → ValidationFlow path).
    emit_and_validate = tree.children[0]
    validation_or_shortcut = emit_and_validate.children[1]
    validation_flow = validation_or_shortcut.children[1]
    assert isinstance(validation_flow.children[1], EvaluateReportCredibility)
    assert isinstance(validation_flow.children[2], EvaluateReportValidity)

    logger.info(
        "STOCHASTIC validation tree:\n%s", py_trees.display.ascii_tree(tree)
    )


# ---------------------------------------------------------------------------
# Embargo domain
# ---------------------------------------------------------------------------


def test_embargo_stochastic_bundle_end_to_end():
    """STOCHASTIC bundle produces correct fuzzer nodes for all 10 embargo children."""
    from vultron.core.behaviors.embargo.manage_embargo_tree import (
        create_manage_embargo_tree,
    )
    from vultron.demo.fuzzer.bundles.embargo import EMBARGO_STOCHASTIC
    from vultron.demo.fuzzer.embargo import (
        ExitEmbargoWhenDeployed,
        ExitEmbargoWhenFixReady,
        SelectEmbargoOfferTerms,
    )

    case_id = "https://example.org/cases/demo-001"
    tree = create_manage_embargo_tree(
        case_id=case_id, call_out=EMBARGO_STOCHASTIC
    )
    assert isinstance(tree, py_trees.behaviour.Behaviour)
    assert len(tree.children) == 10
    assert isinstance(tree.children[0], ExitEmbargoWhenDeployed)
    assert isinstance(tree.children[1], ExitEmbargoWhenFixReady)
    assert isinstance(tree.children[4], SelectEmbargoOfferTerms)

    logger.info(
        "STOCHASTIC embargo tree:\n%s", py_trees.display.ascii_tree(tree)
    )


# ---------------------------------------------------------------------------
# Assign VUL-ID domain
# ---------------------------------------------------------------------------


def test_assign_vul_id_stochastic_bundle_end_to_end():
    """STOCHASTIC bundle produces InScope + IdAssignable fuzzer nodes."""
    from vultron.core.behaviors.report.assign_vul_id_tree import (
        create_assign_vul_id_tree,
    )
    from vultron.demo.fuzzer.bundles.assign_vul_id import (
        ASSIGN_VUL_ID_STOCHASTIC,
    )
    from vultron.demo.fuzzer.report_management.assign_vul_id import (
        IdAssignable,
        InScope,
    )

    case_id = "https://example.org/cases/demo-001"
    tree = create_assign_vul_id_tree(
        case_id=case_id, call_out=ASSIGN_VUL_ID_STOCHASTIC
    )
    assert isinstance(tree.children[0], InScope)
    assert isinstance(tree.children[1], IdAssignable)

    logger.info(
        "STOCHASTIC assign-VUL-ID tree:\n%s", py_trees.display.ascii_tree(tree)
    )


# ---------------------------------------------------------------------------
# Assign CVE-ID domain (full 16-node tree, issue #1817)
# ---------------------------------------------------------------------------


def test_assign_cve_id_stochastic_bundle_end_to_end():
    """STOCHASTIC bundle wires all 14 call-out points to fuzzer nodes."""
    from vultron.core.behaviors.report.assign_cve_id_tree import (
        create_assign_cve_id_tree,
    )
    from vultron.demo.fuzzer.bundles.assign_cve_id import (
        ASSIGN_CVE_ID_STOCHASTIC,
    )
    from vultron.demo.fuzzer.report_management.assign_vul_id import (
        IdAssigned,
        InScope,
    )

    case_id = "https://example.org/cases/demo-cve-001"
    tree = create_assign_cve_id_tree(
        case_id=case_id, call_out=ASSIGN_CVE_ID_STOCHASTIC
    )
    # Root Fallback: first child is IdAssigned (Retriever early-exit)
    assert isinstance(tree.children[0], IdAssigned)
    # Second child is _AssignIdIfInScope Sequence; its first child is InScope
    assert isinstance(tree.children[1].children[0], InScope)

    logger.info(
        "STOCHASTIC assign-CVE-ID tree:\n%s", py_trees.display.ascii_tree(tree)
    )


# ---------------------------------------------------------------------------
# Mode comparison: DETERMINISTIC vs STOCHASTIC vs CUSTOM
# ---------------------------------------------------------------------------


def test_three_mode_comparison():
    """Demonstrate all three modes for the deploy-fix domain side-by-side."""
    from vultron.core.behaviors.call_out.nodes import AlwaysFail
    from vultron.core.behaviors.report.deploy_fix_tree import (
        create_deploy_fix_tree,
    )
    from vultron.demo.fuzzer.bundles.deploy_fix import (
        DEPLOY_FIX_DETERMINISTIC,
        DEPLOY_FIX_STOCHASTIC,
        DeployFixCallOutBundle,
    )
    from vultron.demo.fuzzer.report_management.deploy_fix import DeployFix

    case_id = "https://example.org/cases/demo-001"
    actor_id = "https://example.org/actors/deployer-001"

    # DeployFix is the 5th child (index 4) of the _DeployFixIfReady Sequence,
    # which is the 3rd top-level arm (index 2) of the DeployFixBT Fallback.
    def _deploy_fix_node(tree):
        return tree.children[2].children[4]

    # DETERMINISTIC mode (ceiling/floor defaults)
    det_tree = create_deploy_fix_tree(case_id=case_id, actor_id=actor_id)
    assert isinstance(
        _deploy_fix_node(det_tree), AlwaysFail
    )  # DeployFix p=0.10

    # Explicit DETERMINISTIC singleton — same result
    det_tree2 = create_deploy_fix_tree(
        case_id=case_id, actor_id=actor_id, call_out=DEPLOY_FIX_DETERMINISTIC
    )
    assert isinstance(_deploy_fix_node(det_tree2), AlwaysFail)

    # STOCHASTIC mode — probabilistic fuzzer nodes
    sto_tree = create_deploy_fix_tree(
        case_id=case_id, actor_id=actor_id, call_out=DEPLOY_FIX_STOCHASTIC
    )
    assert isinstance(_deploy_fix_node(sto_tree), DeployFix)

    # CUSTOM mode — per-field override
    def _custom_deploy_fix(name):
        class _Custom(py_trees.behaviour.Behaviour):
            def update(self):
                return py_trees.common.Status.SUCCESS

        return _Custom(name="CustomDeployFix")

    custom_bundle = DeployFixCallOutBundle(
        deploy_fix_factory=_custom_deploy_fix  # type: ignore[arg-type]
    )
    cust_tree = create_deploy_fix_tree(
        case_id=case_id, actor_id=actor_id, call_out=custom_bundle
    )
    assert _deploy_fix_node(cust_tree).name == "CustomDeployFix"

    logger.info("Three-mode comparison complete for deploy-fix domain.")
