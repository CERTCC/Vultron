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

This module provides :func:`create_manage_embargo_tree`, which hosts the ten
embargo management call-out points wired per ADR-0025 / BT-18-004:

Termination nodes:
- ``ExitEmbargoWhenDeployed``
- ``ExitEmbargoWhenFixReady``
- ``ExitEmbargoForOtherReason``

Negotiation / proposal nodes:
- ``StopProposingEmbargo``
- ``SelectEmbargoOfferTerms``
- ``WantToProposeEmbargo``
- ``WillingToCounterEmbargoProposal``
- ``ReasonToProposeEmbargoWhenDeployed``

Proposal evaluation node:
- ``EvaluateEmbargoProposal``

Active embargo evaluation node:
- ``CurrentEmbargoAcceptable``

Phase 1 contains only the injectable call-out points in a stub Sequence.
The full embargo management lifecycle (termination arm, proposal arm,
counter-proposal arm, active-embargo review loop) is deferred to a future
issue.

References
----------
- ADR-0025: ``docs/adr/0025-call-out-point-abstraction-layer.md``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-18-004
"""

import logging

import py_trees

from vultron.core.behaviors.call_out_point import CallOutBackendFactory

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Termination default factories
# ---------------------------------------------------------------------------


def _default_exit_embargo_when_deployed_factory(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.embargo import ExitEmbargoWhenDeployed

    return ExitEmbargoWhenDeployed(name)


def _default_exit_embargo_when_fix_ready_factory(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.embargo import ExitEmbargoWhenFixReady

    return ExitEmbargoWhenFixReady(name)


def _default_exit_embargo_for_other_reason_factory(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.embargo import ExitEmbargoForOtherReason

    return ExitEmbargoForOtherReason(name)


# ---------------------------------------------------------------------------
# Negotiation / proposal default factories
# ---------------------------------------------------------------------------


def _default_stop_proposing_embargo_factory(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.embargo import StopProposingEmbargo

    return StopProposingEmbargo(name)


def _default_select_embargo_offer_terms_factory(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.embargo import SelectEmbargoOfferTerms

    return SelectEmbargoOfferTerms(name)


def _default_want_to_propose_embargo_factory(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.embargo import WantToProposeEmbargo

    return WantToProposeEmbargo(name)


def _default_willing_to_counter_factory(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.embargo import WillingToCounterEmbargoProposal

    return WillingToCounterEmbargoProposal(name)


def _default_reason_to_propose_when_deployed_factory(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.embargo import ReasonToProposeEmbargoWhenDeployed

    return ReasonToProposeEmbargoWhenDeployed(name)


# ---------------------------------------------------------------------------
# Proposal evaluation default factory
# ---------------------------------------------------------------------------


def _default_evaluate_embargo_proposal_factory(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.embargo import EvaluateEmbargoProposal

    return EvaluateEmbargoProposal(name)


# ---------------------------------------------------------------------------
# Active embargo evaluation default factory
# ---------------------------------------------------------------------------


def _default_current_embargo_acceptable_factory(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.embargo import CurrentEmbargoAcceptable

    return CurrentEmbargoAcceptable(name)


# ---------------------------------------------------------------------------
# Tree builder
# ---------------------------------------------------------------------------


def create_manage_embargo_tree(
    case_id: str,
    exit_embargo_when_deployed_factory: CallOutBackendFactory = _default_exit_embargo_when_deployed_factory,
    exit_embargo_when_fix_ready_factory: CallOutBackendFactory = _default_exit_embargo_when_fix_ready_factory,
    exit_embargo_for_other_reason_factory: CallOutBackendFactory = _default_exit_embargo_for_other_reason_factory,
    stop_proposing_embargo_factory: CallOutBackendFactory = _default_stop_proposing_embargo_factory,
    select_embargo_offer_terms_factory: CallOutBackendFactory = _default_select_embargo_offer_terms_factory,
    want_to_propose_embargo_factory: CallOutBackendFactory = _default_want_to_propose_embargo_factory,
    willing_to_counter_factory: CallOutBackendFactory = _default_willing_to_counter_factory,
    reason_to_propose_when_deployed_factory: CallOutBackendFactory = _default_reason_to_propose_when_deployed_factory,
    evaluate_embargo_proposal_factory: CallOutBackendFactory = _default_evaluate_embargo_proposal_factory,
    current_embargo_acceptable_factory: CallOutBackendFactory = _default_current_embargo_acceptable_factory,
) -> py_trees.behaviour.Behaviour:
    """Create behavior tree for the embargo management workflow (Phase 1 stub).

    Phase 1 exposes all ten Evaluator call-out points as a stub Sequence.
    The full embargo management lifecycle (termination arm, proposal arm,
    counter-proposal arm, active-embargo review loop) is deferred to a
    future issue.

    Args:
        case_id: ID of VulnerabilityCase whose embargo is being managed.
        exit_embargo_when_deployed_factory: Factory for the Evaluator that
            decides whether fix deployment is sufficient to end the embargo.
            Defaults to the fuzzer backend (BT-18-004).
        exit_embargo_when_fix_ready_factory: Factory for the Evaluator that
            decides whether fix availability alone ends the embargo.  Defaults
            to the fuzzer backend (BT-18-004).
        exit_embargo_for_other_reason_factory: Factory for the Evaluator that
            handles exceptional embargo exit triggers.  Defaults to the fuzzer
            backend (BT-18-004).
        stop_proposing_embargo_factory: Factory for the Evaluator that decides
            whether to abandon ongoing embargo negotiations.  Defaults to the
            fuzzer backend (BT-18-004).
        select_embargo_offer_terms_factory: Factory for the Evaluator that
            selects terms for a new embargo proposal.  Defaults to the fuzzer
            backend (BT-18-004).
        want_to_propose_embargo_factory: Factory for the Evaluator that decides
            whether to initiate an embargo proposal.  Defaults to the fuzzer
            backend (BT-18-004).
        willing_to_counter_factory: Factory for the Evaluator that decides
            whether to respond to an incoming proposal with a counter-proposal.
            Defaults to the fuzzer backend (BT-18-004).
        reason_to_propose_when_deployed_factory: Factory for the Evaluator
            that handles the rare case of proposing an embargo post-deployment.
            Defaults to the fuzzer backend (BT-18-004).
        evaluate_embargo_proposal_factory: Factory for the Evaluator that
            assesses an incoming embargo proposal.  Defaults to the fuzzer
            backend (BT-18-004).
        current_embargo_acceptable_factory: Factory for the Evaluator that
            decides whether the active embargo terms remain acceptable.
            Defaults to the fuzzer backend (BT-18-004).

    Returns:
        Root node of the manage-embargo behavior tree (Phase 1 stub Sequence).
    """
    root = py_trees.composites.Sequence(
        name="ManageEmbargoBT",
        memory=False,
        children=[
            exit_embargo_when_deployed_factory("ExitEmbargoWhenDeployed"),
            exit_embargo_when_fix_ready_factory("ExitEmbargoWhenFixReady"),
            exit_embargo_for_other_reason_factory("ExitEmbargoForOtherReason"),
            stop_proposing_embargo_factory("StopProposingEmbargo"),
            select_embargo_offer_terms_factory("SelectEmbargoOfferTerms"),
            want_to_propose_embargo_factory("WantToProposeEmbargo"),
            willing_to_counter_factory("WillingToCounterEmbargoProposal"),
            reason_to_propose_when_deployed_factory(
                "ReasonToProposeEmbargoWhenDeployed"
            ),
            evaluate_embargo_proposal_factory("EvaluateEmbargoProposal"),
            current_embargo_acceptable_factory("CurrentEmbargoAcceptable"),
        ],
    )
    logger.info(f"Created ManageEmbargoBT (Phase 1 stub) for case={case_id}")
    return root
