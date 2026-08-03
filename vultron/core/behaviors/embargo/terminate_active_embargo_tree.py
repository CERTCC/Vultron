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
"""Actor-voluntary active embargo termination BT (EMB-14).

Provides :func:`create_terminate_active_embargo_tree`, which models the
production "actor chooses reason, system executes" pattern for voluntarily
exiting an active embargo.

Tree structure::

    Sequence("TerminateActiveEmbargoBT"):
      HasActiveEmbargoNode(case_id)        # precondition guard
      Selector("ReasonSelector"):          # why are we exiting?
        ExitEmbargoWhenDeployed            # Evaluator call-out (EMB-14-001)
        ExitEmbargoWhenFixReady            # Evaluator call-out (EMB-14-001)
        ExitEmbargoForOtherReason          # Evaluator call-out (EMB-14-001)
      Selector("AuthorizeEmbargoExit"):    # are we allowed to proceed?
        EmbargoExitPolicyGuard             # Evaluator call-out (EMB-14-002)
        EmbargoExitOverride                # Evaluator call-out (EMB-14-003)
      OnEmbargoExit                        # Actuator call-out point
      terminate_embargo_bt(case_id, ...)   # existing mechanism (BT-19-001)

References
----------
- Spec: ``specs/em-behavior.yaml`` EMB-14-001, EMB-14-002, EMB-14-003
- ADR-0025: ``docs/adr/0025-call-out-point-abstraction-layer.md``
- Notes: ``notes/bt-fuzzer-nodes-embargo.md`` § EmbargoExitPolicyGuard,
  EmbargoExitOverride
"""

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

import py_trees

from vultron.core.behaviors.embargo.nodes import HasActiveEmbargoNode
from vultron.core.behaviors.embargo.trigger_tree import terminate_embargo_bt

if TYPE_CHECKING:
    from vultron.core.behaviors.call_out.bundles.embargo import (
        EmbargoCallOutBundle,
    )

logger = logging.getLogger(__name__)


def create_terminate_active_embargo_tree(
    *,
    case_id: str,
    result_out: dict[str, object],
    activity_builder: Callable[[str], list[str]] | None = None,
    call_out: "EmbargoCallOutBundle | None" = None,
) -> py_trees.behaviour.Behaviour:
    """Create the actor-voluntary active embargo termination BT (EMB-14).

    Models the production "actor chooses reason, system executes" pattern:

    1. Guard that an active embargo exists (precondition).
    2. Reason Selector — one of three Evaluator call-out points must return
       SUCCESS to supply a termination reason (EMB-14-001).
    3. Authorization Selector — EmbargoExitPolicyGuard (happy path, EMB-14-002)
       or EmbargoExitOverride (audit-trail fallback, EMB-14-003) must allow the
       exit to proceed.
    4. OnEmbargoExit Actuator fires integration hooks before state mutation.
    5. ``terminate_embargo_bt`` performs the actual EM state transition and
       activity dispatch (BT-19-001).

    Args:
        case_id: ID of the VulnerabilityCase whose active embargo to terminate.
        result_out: Mutable dict for BT result propagation; passed to
            :func:`~vultron.core.behaviors.embargo.trigger_tree.terminate_embargo_bt`.
        activity_builder: Optional activity builder for the trigger path.
            ``None`` uses the cascade path (SendTerminateEmbargoActivityNode).
            Forwarded to :func:`terminate_embargo_bt`.
        call_out: Bundle of call-out backend factories for this domain.
            Defaults to
            :data:`~vultron.core.behaviors.call_out.bundles.embargo.EMBARGO_DETERMINISTIC`
            (BT-23-003, BT-23-005).

    Returns:
        Root node of the terminate-active-embargo behavior tree.
    """
    from vultron.core.behaviors.call_out.bundles.embargo import (
        EMBARGO_DETERMINISTIC,
    )

    bundle = call_out if call_out is not None else EMBARGO_DETERMINISTIC

    reason_selector = py_trees.composites.Selector(
        name="ReasonSelector",
        memory=False,
        children=[
            bundle.exit_embargo_when_deployed_factory(
                "ExitEmbargoWhenDeployed"
            ),
            bundle.exit_embargo_when_fix_ready_factory(
                "ExitEmbargoWhenFixReady"
            ),
            bundle.exit_embargo_for_other_reason_factory(
                "ExitEmbargoForOtherReason"
            ),
        ],
    )

    authorize_selector = py_trees.composites.Selector(
        name="AuthorizeEmbargoExit",
        memory=False,
        children=[
            bundle.embargo_exit_policy_guard_factory("EmbargoExitPolicyGuard"),
            bundle.embargo_exit_override_factory("EmbargoExitOverride"),
        ],
    )

    root = py_trees.composites.Sequence(
        name="TerminateActiveEmbargoBT",
        memory=False,
        children=[
            HasActiveEmbargoNode(case_id=case_id, result_out=result_out),
            reason_selector,
            authorize_selector,
            bundle.on_embargo_exit_factory("OnEmbargoExit"),
            terminate_embargo_bt(
                case_id=case_id,
                result_out=result_out,
                activity_builder=activity_builder,
            ),
        ],
    )

    logger.info("Created TerminateActiveEmbargoBT for case=%s", case_id)
    return root
