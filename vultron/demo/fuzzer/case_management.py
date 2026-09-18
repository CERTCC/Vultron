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

"""Probabilistic fuzzer nodes for the Case Management workflow.

This module provides probabilistic stub ``py_trees`` behaviour nodes for
case-management call-out points — currently the admission decision a case actor
service makes on an inbound ``Create(as_CaseProposal)``.

Nodes are built on the probabilistic base types in
``vultron.demo.fuzzer.base`` and satisfy BT-16-003 (named integration-point
nodes with semantic docstrings) and BT-16-005 (automation-potential
categorization).

References
----------
- Spec: ``specs/case-proposal.yaml`` CP-05-002
- Spec: ``specs/behavior-tree-integration.yaml`` BT-16-003, BT-16-005, BT-18-001
"""

from __future__ import annotations

from vultron.demo.fuzzer.base import AlmostAlwaysSucceed
from vultron.demo.fuzzer.call_out_point import EvaluatorCallOutPoint


class EvaluateCaseProposal(EvaluatorCallOutPoint, AlmostAlwaysSucceed):
    """Decide whether to admit an inbound ``Create(as_CaseProposal)``.

    Semantic function:
        Condition — a case actor service reviews a proposal and decides
        whether to open and manage a case for it (CP-05-002).  This is the
        only place admission policy lives: whether the proposing actor is
        recognised, whether it already holds more open cases than the service
        will carry, and whether the inline report is substantive enough to
        coordinate.  Modeled as almost always succeeding, because declining a
        proposal is the exceptional outcome for a service an actor was
        configured to trust.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates the proposal from the caller's DataLayer)
      Output keys: evaluate_case_proposal_verdict: str  (SUCCESS only)

    Input category: Human decision / policy evaluation.

    Success probability: 0.90 (``AlmostAlwaysSucceed``).

    Automation potential: **Medium** — allow-list and open-case-count checks
    are fully automatable; judging whether a report is substantive enough to
    warrant a coordinated case typically needs human review.
    """

    output_keys = {"evaluate_case_proposal_verdict": str}


__all__ = ["EvaluateCaseProposal"]
