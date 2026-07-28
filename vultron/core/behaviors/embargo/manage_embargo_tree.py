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
"""Embargo management behavior tree composition (Phase 1 stub).

This module provides :func:`create_manage_embargo_tree`, which hosts the
embargo management call-out points wired per ADR-0025 / BT-18-004:

Termination nodes (Evaluator):
- ``ExitEmbargoWhenDeployed``
- ``ExitEmbargoWhenFixReady``
- ``ExitEmbargoForOtherReason``

Negotiation / proposal nodes (Evaluator):
- ``StopProposingEmbargo``
- ``SelectEmbargoOfferTerms``
- ``WantToProposeEmbargo``
- ``WillingToCounterEmbargoProposal``
- ``ReasonToProposeEmbargoWhenDeployed``

Proposal evaluation node (Evaluator):
- ``EvaluateEmbargoProposal``

Active embargo evaluation node (Evaluator):
- ``CurrentEmbargoAcceptable``

Actuator nodes (reserved for Phase 2 — accepted but not yet wired):
- ``OnEmbargoExit``
- ``OnEmbargoAccept``
- ``OnEmbargoReject``

Phase 1 contains only the Evaluator call-out points in a stub Sequence.
The full embargo management lifecycle (termination arm, proposal arm,
counter-proposal arm, active-embargo review loop) is deferred to a future
issue.

References
----------
- ADR-0025: ``docs/adr/0025-call-out-point-abstraction-layer.md``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-18-004
"""

import logging
from typing import TYPE_CHECKING

import py_trees

if TYPE_CHECKING:
    from vultron.demo.fuzzer.bundles.embargo import EmbargoCallOutBundle

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tree builder
# ---------------------------------------------------------------------------


def create_manage_embargo_tree(
    case_id: str,
    call_out: "EmbargoCallOutBundle | None" = None,
) -> py_trees.behaviour.Behaviour:
    """Create behavior tree for the embargo management workflow (Phase 1 stub).

    Phase 1 exposes all ten Evaluator call-out points as a stub Sequence.
    The three Actuator factories (on_embargo_exit_factory,
    on_embargo_accept_factory, on_embargo_reject_factory) in the bundle are
    reserved for Phase 2 when the full termination, acceptance, and rejection
    arms are built.  The full embargo management lifecycle is deferred to a
    future issue.

    Args:
        case_id: ID of VulnerabilityCase whose embargo is being managed.
        call_out: Bundle of call-out backend factories for this domain.
            Defaults to :data:`~vultron.demo.fuzzer.bundles.embargo.EMBARGO_DETERMINISTIC`
            (BT-23-003, BT-23-005).

    Returns:
        Root node of the manage-embargo behavior tree (Phase 1 stub Sequence).
    """
    from vultron.demo.fuzzer.bundles.embargo import EMBARGO_DETERMINISTIC

    bundle = call_out if call_out is not None else EMBARGO_DETERMINISTIC
    # Phase 2: bundle.on_embargo_exit_factory, bundle.on_embargo_accept_factory,
    # and bundle.on_embargo_reject_factory are reserved for the full termination,
    # acceptance, and rejection workflow arms.
    root = py_trees.composites.Sequence(
        name="ManageEmbargoBT",
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
            bundle.stop_proposing_embargo_factory("StopProposingEmbargo"),
            bundle.select_embargo_offer_terms_factory(
                "SelectEmbargoOfferTerms"
            ),
            bundle.want_to_propose_embargo_factory("WantToProposeEmbargo"),
            bundle.willing_to_counter_factory(
                "WillingToCounterEmbargoProposal"
            ),
            bundle.reason_to_propose_when_deployed_factory(
                "ReasonToProposeEmbargoWhenDeployed"
            ),
            bundle.evaluate_embargo_proposal_factory(
                "EvaluateEmbargoProposal"
            ),
            bundle.current_embargo_acceptable_factory(
                "CurrentEmbargoAcceptable"
            ),
        ],
    )
    logger.info(f"Created ManageEmbargoBT (Phase 1 stub) for case={case_id}")
    return root
