"""Embargo management fuzzer nodes for the Vultron demo layer.

This module provides probabilistic stub ``py_trees`` behaviour nodes for the
Embargo Management (EM) workflow.  Each node represents an external-dependency
touchpoint — a human decision, environmental check, or system integration
hook — that will eventually be replaced by production logic.

Nodes are built on the probabilistic base types in
``vultron.demo.fuzzer.base`` and satisfy BT-16-003 and BT-16-007 (named
integration-point nodes with semantic docstrings) and BT-16-005 (automation-potential
categorization).

References
----------
- Source: ``vultron/bt/embargo_management/fuzzer.py``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-16-003, BT-16-004, BT-16-005
- Catalog: ``docs/developer/reference/bt-fuzzer/embargo.md``
"""

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

from vultron.demo.fuzzer.embargo.evaluation import (
    CurrentEmbargoAcceptable,
    EvaluateEmbargoProposal,
    OnEmbargoAccept,
    OnEmbargoReject,
)
from vultron.demo.fuzzer.embargo.proposal import (
    AvoidEmbargoCounterProposal,
    ReasonToProposeEmbargoWhenDeployed,
    SelectEmbargoOfferTerms,
    StopProposingEmbargo,
    WantToProposeEmbargo,
    WillingToCounterEmbargoProposal,
)
from vultron.demo.fuzzer.embargo.termination import (
    EmbargoExitOverride,
    EmbargoExitPolicyGuard,
    EmbargoTimerExpired,
    ExitEmbargoForOtherReason,
    ExitEmbargoWhenDeployed,
    ExitEmbargoWhenFixReady,
    OnEmbargoExit,
)

__all__ = [
    "AvoidEmbargoCounterProposal",
    "CurrentEmbargoAcceptable",
    "EmbargoExitOverride",
    "EmbargoExitPolicyGuard",
    "EmbargoTimerExpired",
    "EvaluateEmbargoProposal",
    "ExitEmbargoForOtherReason",
    "ExitEmbargoWhenDeployed",
    "ExitEmbargoWhenFixReady",
    "OnEmbargoAccept",
    "OnEmbargoExit",
    "OnEmbargoReject",
    "ReasonToProposeEmbargoWhenDeployed",
    "SelectEmbargoOfferTerms",
    "StopProposingEmbargo",
    "WantToProposeEmbargo",
    "WillingToCounterEmbargoProposal",
]
