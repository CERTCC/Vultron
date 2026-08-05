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
"""Deployment combinator behavior tree (BT-20-005 SHOULD).

This module provides :func:`create_deploy_tree`, which composes the overarching
deployment decision as a ``DeployOrMitigateBT`` Fallback:

.. code-block:: text

    DeployOrMitigateBT (Fallback)
    ├─ create_deploy_fix_tree(...)        # fix arm — preferred
    └─ create_deploy_mitigation_tree(...) # mitigation arm — fallback

The fix arm is attempted first; if it fails the mitigation arm runs as a
fallback.  Each arm is a fully independent subtree with its own call-out bundle.

References
----------
- Issue: #1985
- Spec: ``specs/behavior-tree-integration.yaml`` BT-20-005
- Notes: ``notes/bt-fuzzer-rm-fix.md`` § "Combinator tree"
- ADR-0025: ``docs/adr/0025-call-out-point-abstraction-layer.md``
"""

import logging
from typing import TYPE_CHECKING

import py_trees

from vultron.core.behaviors.report.deploy_fix_tree import (
    create_deploy_fix_tree,
)
from vultron.core.behaviors.report.deploy_mitigation_tree import (
    create_deploy_mitigation_tree,
)

if TYPE_CHECKING:
    from vultron.core.behaviors.call_out.bundles.deploy_fix import (
        DeployFixCallOutBundle,
    )
    from vultron.core.behaviors.call_out.bundles.deploy_mitigation import (
        DeployMitigationCallOutBundle,
    )

logger = logging.getLogger(__name__)


def create_deploy_tree(
    case_id: str,
    actor_id: str,
    fix_call_out: "DeployFixCallOutBundle | None" = None,
    mitigation_call_out: "DeployMitigationCallOutBundle | None" = None,
) -> py_trees.behaviour.Behaviour:
    """Create the deployment combinator behavior tree (BT-20-005).

    Composes the fix and mitigation deployment subtrees into a single
    ``DeployOrMitigateBT`` Fallback.  The fix arm is preferred; the mitigation
    arm runs only when the fix arm fails.

    Args:
        case_id: ID of VulnerabilityCase being processed.
        actor_id: ID of the actor running this tree.
        fix_call_out: Call-out bundle for the fix deployment arm.  Defaults to
            :data:`~vultron.core.behaviors.call_out.bundles.deploy_fix.DEPLOY_FIX_DETERMINISTIC`.
        mitigation_call_out: Call-out bundle for the mitigation deployment arm.
            Defaults to
            :data:`~vultron.core.behaviors.call_out.bundles.deploy_mitigation.DEPLOY_MITIGATION_DETERMINISTIC`.

    Returns:
        Root node of the deploy-or-mitigate behavior tree (Fallback).
    """
    fix_arm = create_deploy_fix_tree(
        case_id=case_id, actor_id=actor_id, call_out=fix_call_out
    )
    mitigation_arm = create_deploy_mitigation_tree(
        case_id=case_id, actor_id=actor_id, call_out=mitigation_call_out
    )

    root = py_trees.composites.Selector(
        name="DeployOrMitigateBT",
        memory=False,
        children=[fix_arm, mitigation_arm],
    )

    logger.info(
        "Created DeployOrMitigateBT for case=%s actor=%s", case_id, actor_id
    )
    return root
