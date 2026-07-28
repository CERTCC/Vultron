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
"""Call-out bundle for the embargo management domain (BT-23-003, BT-23-005).

Provides :class:`EmbargoCallOutBundle` plus the pre-built singletons
:data:`EMBARGO_DETERMINISTIC` and :data:`EMBARGO_STOCHASTIC`.

Ceiling/floor mapping (BT-23-002):

- ``exit_embargo_when_deployed_factory``       — ExitEmbargoWhenDeployed       (p=0.33) → AlwaysFail
- ``exit_embargo_when_fix_ready_factory``      — ExitEmbargoWhenFixReady       (p=0.25) → AlwaysFail
- ``exit_embargo_for_other_reason_factory``    — ExitEmbargoForOtherReason     (p=0.005) → AlwaysFail
- ``stop_proposing_embargo_factory``           — StopProposingEmbargo          (p=0.25) → AlwaysFail
- ``select_embargo_offer_terms_factory``       — SelectEmbargoOfferTerms       (p=1.0) → AlwaysSucceed
- ``want_to_propose_embargo_factory``          — WantToProposeEmbargo          (p=0.50) → AlwaysSucceed (tie-break)
- ``willing_to_counter_factory``               — WillingToCounterEmbargoProposal (p=0.25) → AlwaysFail
- ``reason_to_propose_when_deployed_factory``  — ReasonToProposeEmbargoWhenDeployed (p=0.07) → AlwaysFail
- ``evaluate_embargo_proposal_factory``        — EvaluateEmbargoProposal       (p=0.75) → AlwaysSucceed
- ``current_embargo_acceptable_factory``       — CurrentEmbargoAcceptable      (p=0.90) → AlwaysSucceed
- ``on_embargo_exit_factory``                  — OnEmbargoExit                 (p=1.0) → AlwaysSucceed
- ``on_embargo_accept_factory``                — OnEmbargoAccept               (p=1.0) → AlwaysSucceed
- ``on_embargo_reject_factory``                — OnEmbargoReject               (p=1.0) → AlwaysSucceed
"""

from __future__ import annotations

from dataclasses import dataclass, field

import py_trees

from vultron.core.behaviors.call_out_point import CallOutBackendFactory


def _always_succeed(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.base import AlwaysSucceed

    return AlwaysSucceed(name)


def _always_fail(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.base import AlwaysFail

    return AlwaysFail(name)


def _stochastic_exit_when_deployed(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.embargo import ExitEmbargoWhenDeployed

    return ExitEmbargoWhenDeployed(name)


def _stochastic_exit_when_fix_ready(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.embargo import ExitEmbargoWhenFixReady

    return ExitEmbargoWhenFixReady(name)


def _stochastic_exit_for_other_reason(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.embargo import ExitEmbargoForOtherReason

    return ExitEmbargoForOtherReason(name)


def _stochastic_stop_proposing(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.embargo import StopProposingEmbargo

    return StopProposingEmbargo(name)


def _stochastic_select_terms(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.embargo import SelectEmbargoOfferTerms

    return SelectEmbargoOfferTerms(name)


def _stochastic_want_to_propose(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.embargo import WantToProposeEmbargo

    return WantToProposeEmbargo(name)


def _stochastic_willing_to_counter(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.embargo import WillingToCounterEmbargoProposal

    return WillingToCounterEmbargoProposal(name)


def _stochastic_reason_to_propose_when_deployed(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.embargo import ReasonToProposeEmbargoWhenDeployed

    return ReasonToProposeEmbargoWhenDeployed(name)


def _stochastic_evaluate_proposal(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.embargo import EvaluateEmbargoProposal

    return EvaluateEmbargoProposal(name)


def _stochastic_current_acceptable(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.embargo import CurrentEmbargoAcceptable

    return CurrentEmbargoAcceptable(name)


def _stochastic_on_exit(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.embargo import OnEmbargoExit

    return OnEmbargoExit(name)


def _stochastic_on_accept(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.embargo import OnEmbargoAccept

    return OnEmbargoAccept(name)


def _stochastic_on_reject(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.embargo import OnEmbargoReject

    return OnEmbargoReject(name)


@dataclass(frozen=True)
class EmbargoCallOutBundle:
    """Call-out backend bundle for the embargo management domain (BT-23-003).

    Fields map to the corresponding factory parameters on
    :func:`~vultron.core.behaviors.embargo.manage_embargo_tree.create_manage_embargo_tree`.
    """

    exit_embargo_when_deployed_factory: CallOutBackendFactory = field(
        default=_always_fail  # type: ignore[assignment]
    )
    exit_embargo_when_fix_ready_factory: CallOutBackendFactory = field(
        default=_always_fail  # type: ignore[assignment]
    )
    exit_embargo_for_other_reason_factory: CallOutBackendFactory = field(
        default=_always_fail  # type: ignore[assignment]
    )
    stop_proposing_embargo_factory: CallOutBackendFactory = field(
        default=_always_fail  # type: ignore[assignment]
    )
    select_embargo_offer_terms_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    want_to_propose_embargo_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    willing_to_counter_factory: CallOutBackendFactory = field(
        default=_always_fail  # type: ignore[assignment]
    )
    reason_to_propose_when_deployed_factory: CallOutBackendFactory = field(
        default=_always_fail  # type: ignore[assignment]
    )
    evaluate_embargo_proposal_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    current_embargo_acceptable_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    on_embargo_exit_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    on_embargo_accept_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    on_embargo_reject_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )


EMBARGO_DETERMINISTIC = EmbargoCallOutBundle()
"""Deterministic bundle: ceiling/floor of stochastic p (BT-23-001, BT-23-002)."""

EMBARGO_STOCHASTIC = EmbargoCallOutBundle(
    exit_embargo_when_deployed_factory=_stochastic_exit_when_deployed,  # type: ignore[arg-type]
    exit_embargo_when_fix_ready_factory=_stochastic_exit_when_fix_ready,  # type: ignore[arg-type]
    exit_embargo_for_other_reason_factory=_stochastic_exit_for_other_reason,  # type: ignore[arg-type]
    stop_proposing_embargo_factory=_stochastic_stop_proposing,  # type: ignore[arg-type]
    select_embargo_offer_terms_factory=_stochastic_select_terms,  # type: ignore[arg-type]
    want_to_propose_embargo_factory=_stochastic_want_to_propose,  # type: ignore[arg-type]
    willing_to_counter_factory=_stochastic_willing_to_counter,  # type: ignore[arg-type]
    reason_to_propose_when_deployed_factory=_stochastic_reason_to_propose_when_deployed,  # type: ignore[arg-type]
    evaluate_embargo_proposal_factory=_stochastic_evaluate_proposal,  # type: ignore[arg-type]
    current_embargo_acceptable_factory=_stochastic_current_acceptable,  # type: ignore[arg-type]
    on_embargo_exit_factory=_stochastic_on_exit,  # type: ignore[arg-type]
    on_embargo_accept_factory=_stochastic_on_accept,  # type: ignore[arg-type]
    on_embargo_reject_factory=_stochastic_on_reject,  # type: ignore[arg-type]
)
"""Stochastic bundle: all nodes use probabilistic fuzzer classes."""

__all__ = [
    "EmbargoCallOutBundle",
    "EMBARGO_DETERMINISTIC",
    "EMBARGO_STOCHASTIC",
]
