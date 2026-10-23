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
"""Call-out bundle for the case-proposal admission domain (BT-23-003, BT-23-005).

Provides :class:`CaseProposalCallOutBundle` and the pre-built core DETERMINISTIC
singleton :data:`CASE_PROPOSAL_DETERMINISTIC`.  The matching STOCHASTIC singleton
lives in the simulation layer
(:data:`vultron.demo.fuzzer.bundles.case_proposal.CASE_PROPOSAL_STOCHASTIC`).

The single call-out point in this domain is the admission decision a case actor
service makes on an inbound ``Create(as_CaseProposal)`` (CP-05-002).  It is the
only place a deployment can express admission policy — who may propose, how many
open cases one actor may hold, whether the inline report is acceptable.

Ceiling/floor mapping (BT-23-002):

- ``evaluate_proposal_factory`` — EvaluateCaseProposal (p=0.90) → AlwaysSucceed

The permissive default is deliberate and is *not* covered by the BT-23-012
conservative-default carve-out.  BT-23-012 governs gates whose permissive
backend would let a party other than the Case Owner force canonical case-state
adoption or embargo teardown on an *existing* case.  Accepting a proposal
creates a *new* case in which the proposing actor becomes the CASE_OWNER, so no
other party's agreed state is touched.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import py_trees

from vultron.core.behaviors.call_out.bundles.base import CallOutBundle
from vultron.core.behaviors.call_out.nodes import AlwaysSucceed
from vultron.core.behaviors.call_out.protocol import CallOutBackendFactory


def _always_succeed(name: str) -> py_trees.behaviour.Behaviour:
    return AlwaysSucceed(name)


@dataclass(frozen=True)
class CaseProposalCallOutBundle(CallOutBundle):
    """Call-out backend bundle for the case-proposal domain (BT-23-003).

    Fields map to the corresponding factory parameters on
    :func:`~vultron.core.behaviors.case.case_proposal_received_tree.create_case_proposal_received_tree`.
    """

    evaluate_proposal_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )


CASE_PROPOSAL_DETERMINISTIC = CaseProposalCallOutBundle()
"""Deterministic bundle: admission always succeeds (BT-23-001, BT-23-002)."""

__all__ = [
    "CaseProposalCallOutBundle",
    "CASE_PROPOSAL_DETERMINISTIC",
]
