#!/usr/bin/env python
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
"""Demo fuzzer package — probabilistic py_trees behaviour nodes."""

from vultron.demo.fuzzer.base import (
    AlmostAlwaysFail,
    AlmostAlwaysSucceed,
    AlmostCertainlyFail,
    AlmostCertainlySucceed,
    AlwaysFail,
    AlwaysSucceed,
    LikelyFail,
    LikelySucceed,
    OftenFail,
    OftenSucceed,
    OneInOneHundred,
    OneInTwenty,
    OneInTwoHundred,
    ProbablyFail,
    ProbablySucceed,
    RandomActionNode,
    RandomConditionNode,
    RandomSucceedFail,
    RarelySucceed,
    SuccessOrRunning,
    UniformSucceedFail,
    UsuallyFail,
    UsuallySucceed,
    WeightedBehavior,
)
from vultron.demo.fuzzer.messaging import FollowUpOnErrorMessage
from vultron.demo.fuzzer.report_management import (
    EnoughPrioritizationInfo,
    EnoughValidationInfo,
    EvaluateReportCredibility,
    EvaluateReportValidity,
    GatherPrioritizationInfo,
    GatherValidationInfo,
    NoNewPrioritizationInfo,
    NoNewValidationInfo,
    OnAccept,
    OnDefer,
)
from vultron.demo.fuzzer.embargo import (
    AvoidEmbargoCounterProposal,
    CurrentEmbargoAcceptable,
    EmbargoTimerExpired,
    EvaluateEmbargoProposal,
    ExitEmbargoForOtherReason,
    ExitEmbargoWhenDeployed,
    ExitEmbargoWhenFixReady,
    OnEmbargoAccept,
    OnEmbargoExit,
    OnEmbargoReject,
    ReasonToProposeEmbargoWhenDeployed,
    SelectEmbargoOfferTerms,
    StopProposingEmbargo,
    WantToProposeEmbargo,
    WillingToCounterEmbargoProposal,
)

__all__ = [
    # base types
    "WeightedBehavior",
    "SuccessOrRunning",
    "AlwaysSucceed",
    "AlwaysFail",
    "AlmostCertainlySucceed",
    "AlmostAlwaysSucceed",
    "UsuallySucceed",
    "OftenSucceed",
    "LikelySucceed",
    "ProbablySucceed",
    "UniformSucceedFail",
    "RandomSucceedFail",
    "ProbablyFail",
    "OftenFail",
    "UsuallyFail",
    "AlmostAlwaysFail",
    "RarelySucceed",
    "AlmostCertainlyFail",
    "OneInTwenty",
    "OneInOneHundred",
    "OneInTwoHundred",
    "LikelyFail",
    "RandomConditionNode",
    "RandomActionNode",
    # embargo management nodes
    "ExitEmbargoWhenDeployed",
    "ExitEmbargoWhenFixReady",
    "ExitEmbargoForOtherReason",
    "EmbargoTimerExpired",
    "OnEmbargoExit",
    "StopProposingEmbargo",
    "SelectEmbargoOfferTerms",
    "WantToProposeEmbargo",
    "WillingToCounterEmbargoProposal",
    "AvoidEmbargoCounterProposal",
    "ReasonToProposeEmbargoWhenDeployed",
    "EvaluateEmbargoProposal",
    "OnEmbargoAccept",
    "OnEmbargoReject",
    "CurrentEmbargoAcceptable",
    # report validation nodes
    "NoNewValidationInfo",
    "EvaluateReportCredibility",
    "EvaluateReportValidity",
    "EnoughValidationInfo",
    "GatherValidationInfo",
    # report prioritization nodes
    "NoNewPrioritizationInfo",
    "EnoughPrioritizationInfo",
    "GatherPrioritizationInfo",
    "OnAccept",
    "OnDefer",
    # messaging inbound nodes
    "FollowUpOnErrorMessage",
]
