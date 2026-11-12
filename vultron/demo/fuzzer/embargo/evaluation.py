"""Embargo proposal, inbound-response and active-embargo evaluation fuzzer nodes."""

#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
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

from __future__ import annotations

from vultron.core.behaviors.call_out.capabilities.embargo.evaluation import (
    CurrentEmbargoAcceptableCapability,
    EvaluateEmbargoProposalCapability,
    OnEmbargoAcceptCapability,
    OnEmbargoRejectCapability,
)
from vultron.demo.fuzzer.base import (
    AlmostAlwaysSucceed,
    AlwaysSucceed,
    UsuallySucceed,
)

# ---------------------------------------------------------------------------
# Embargo proposal evaluation nodes
# ---------------------------------------------------------------------------


class EvaluateEmbargoProposal(
    EvaluateEmbargoProposalCapability, UsuallySucceed
):
    """Assess an incoming embargo proposal and decide whether to accept it.

    Simulates :class:`EvaluateEmbargoProposalCapability`,
    whose ports are its blackboard contract (BT-18-021).

    Semantic function:
        Condition/action — review the proposed terms and determine whether
        they are acceptable.  In production may involve automated policy
        compatibility checks or structured human analyst review.  Modeled
        as usually succeeding (acceptance is the common outcome).

    Input category: Human decision.

    Success probability: 0.75 (``UsuallySucceed``).

    Automation potential: **Medium** — basic compatibility check (is the
    proposed duration within policy bounds?) is automatable; final
    accept/reject for out-of-range proposals typically needs human review.
    """


class OnEmbargoAccept(OnEmbargoAcceptCapability, AlwaysSucceed):
    """Execute site-specific tasks when an embargo proposal is accepted.

    Simulates :class:`OnEmbargoAcceptCapability`,
    whose ports are its blackboard contract (BT-18-021).

    Semantic function:
        Action integration hook — notify stakeholders, record the
        agreement, and start the embargo timer when the proposal is
        accepted.  Must be idempotent in production.

    Input category: System integration.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **High** — notification dispatch, timer
    initialization, and state-update actions are fully automatable via
    APIs.
    """


class OnEmbargoReject(OnEmbargoRejectCapability, AlwaysSucceed):
    """Execute site-specific tasks when an embargo proposal is rejected.

    Simulates :class:`OnEmbargoRejectCapability`,
    whose ports are its blackboard contract (BT-18-021).

    Semantic function:
        Action integration hook — notify stakeholders and log the
        rejection rationale when the proposal is not accepted.  Must be
        idempotent in production.

    Input category: System integration.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **High** — notification dispatch and logging
    actions are fully automatable via APIs.
    """


# ---------------------------------------------------------------------------
# Active embargo evaluation nodes
# ---------------------------------------------------------------------------


class CurrentEmbargoAcceptable(
    CurrentEmbargoAcceptableCapability, AlmostAlwaysSucceed
):
    """Decide whether the current active embargo terms remain acceptable.

    Simulates :class:`CurrentEmbargoAcceptableCapability`,
    whose ports are its blackboard contract (BT-18-021).

    Semantic function:
        Condition — is the participant satisfied with the current active
        embargo, or do they wish to propose a revision?  Modeled as
        usually acceptable; revision proposals are relatively uncommon.

    Input category: Human decision.

    Success probability: 0.90 (``AlmostAlwaysSucceed``).

    Automation potential: **Medium** — automated comparison of current
    terms against policy preferences is feasible; edge cases and dynamic
    negotiation contexts may still require human judgment.
    """
