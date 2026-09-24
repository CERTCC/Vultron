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
"""STOCHASTIC call-out bundle for the case-proposal domain (BT-23-003, BT-23-009).

Provides the simulation-layer :data:`CASE_PROPOSAL_STOCHASTIC` singleton, which
wires the probabilistic ``WeightedBehavior`` fuzzer node into the core-owned
:class:`~vultron.core.behaviors.call_out.bundles.case_proposal.CaseProposalCallOutBundle`.

The bundle dataclass and the DETERMINISTIC default are core concerns and live in
``vultron.core.behaviors.call_out.bundles.case_proposal``; they are re-exported
here for backward-compatible import paths.

Ceiling/floor mapping for the DETERMINISTIC counterpart (BT-23-002):

- ``evaluate_proposal_factory`` — EvaluateCaseProposal (p=0.90) → AlwaysSucceed
"""

from __future__ import annotations

import py_trees

# Core-owned bundle dataclass + DETERMINISTIC default (re-exported for
# backward-compatible import paths).
from vultron.core.behaviors.call_out.bundles.case_proposal import (  # noqa: F401
    CASE_PROPOSAL_DETERMINISTIC,
    CaseProposalCallOutBundle,
)


def _stochastic_evaluate_proposal(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.case_management import EvaluateCaseProposal

    return EvaluateCaseProposal(name)


CASE_PROPOSAL_STOCHASTIC = CaseProposalCallOutBundle(
    evaluate_proposal_factory=_stochastic_evaluate_proposal,  # type: ignore[arg-type]
)
"""Stochastic bundle: admission uses the probabilistic fuzzer class."""

__all__ = [
    "CaseProposalCallOutBundle",
    "CASE_PROPOSAL_DETERMINISTIC",
    "CASE_PROPOSAL_STOCHASTIC",
]
