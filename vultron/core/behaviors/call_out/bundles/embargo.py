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

Provides :class:`EmbargoCallOutBundle` and the pre-built core DETERMINISTIC
singleton :data:`EMBARGO_DETERMINISTIC`.  The matching STOCHASTIC singleton
lives in the simulation layer
(:data:`vultron.demo.fuzzer.bundles.embargo.EMBARGO_STOCHASTIC`).

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
- ``embargo_exit_policy_guard_factory``        — EmbargoExitPolicyGuard        (p=1.0) → AlwaysSucceed
- ``embargo_exit_override_factory``            — EmbargoExitOverride           (p=0.0) → AlwaysFail
"""

from __future__ import annotations

from dataclasses import dataclass, field

import py_trees

from vultron.core.behaviors.call_out.nodes import AlwaysFail, AlwaysSucceed
from vultron.core.behaviors.call_out.protocol import CallOutBackendFactory


def _always_succeed(name: str) -> py_trees.behaviour.Behaviour:
    return AlwaysSucceed(name)


def _always_fail(name: str) -> py_trees.behaviour.Behaviour:
    return AlwaysFail(name)


@dataclass(frozen=True)
class EmbargoCallOutBundle:
    """Call-out backend bundle for the embargo management domain (BT-23-003).

    Fields map to the corresponding factory parameters on
    :func:`~vultron.core.behaviors.embargo.manage_embargo_tree.create_manage_embargo_tree`
    and (for termination-specific fields) the future
    ``create_terminate_active_embargo_tree`` factory (issue #1256).
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
    embargo_exit_policy_guard_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    embargo_exit_override_factory: CallOutBackendFactory = field(
        default=_always_fail  # type: ignore[assignment]
    )


EMBARGO_DETERMINISTIC = EmbargoCallOutBundle()
"""Deterministic bundle: ceiling/floor of stochastic p (BT-23-001, BT-23-002)."""

__all__ = [
    "EmbargoCallOutBundle",
    "EMBARGO_DETERMINISTIC",
]
