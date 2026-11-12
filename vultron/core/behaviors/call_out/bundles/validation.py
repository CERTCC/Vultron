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
"""Call-out bundle for the report validation domain (BT-23-003, BT-23-005).

Provides :class:`ValidationCallOutBundle` and the pre-built core DETERMINISTIC
singleton :data:`VALIDATION_DETERMINISTIC`.  The matching STOCHASTIC singleton
lives in the simulation layer
(:data:`vultron.demo.fuzzer.bundles.validation.VALIDATION_STOCHASTIC`).

Ceiling/floor mapping (BT-23-002):

- ``credibility_factory``   — EvaluateReportCredibility (p=0.90) → AlwaysSucceed
- ``validity_factory``      — EvaluateReportValidity    (p=0.90) → AlwaysSucceed
- ``gather_info_factory``   — GatherValidationInfo      (p=0.90) → AlwaysSucceed
"""

from __future__ import annotations

from dataclasses import dataclass, field

from vultron.core.behaviors.call_out.bundles.base import CallOutBundle
from vultron.core.behaviors.call_out.capabilities.report_management.validate import (
    EvaluateReportCredibilityCapability,
    EvaluateReportValidityCapability,
    GatherValidationInfoCapability,
)
from vultron.core.behaviors.call_out.nodes import (
    always_succeed_as,
)
from vultron.core.behaviors.call_out.protocol import CallOutBackendFactory


@dataclass(frozen=True)
class ValidationCallOutBundle(CallOutBundle):
    """Call-out backend bundle for the report validation domain (BT-23-003).

    Fields map to the corresponding factory parameters on
    :func:`~vultron.core.behaviors.report.validate_tree.create_validate_report_tree`.
    """

    credibility_factory: CallOutBackendFactory = field(
        default=always_succeed_as(EvaluateReportCredibilityCapability)  # type: ignore[assignment]
    )
    validity_factory: CallOutBackendFactory = field(
        default=always_succeed_as(EvaluateReportValidityCapability)  # type: ignore[assignment]
    )
    gather_info_factory: CallOutBackendFactory = field(
        default=always_succeed_as(GatherValidationInfoCapability)  # type: ignore[assignment]
    )
    """GatherValidationInfo (Retriever): p=0.90 → AlwaysSucceed.

    Store-held answer (BT-18-039): **cannot**.  It collects outside
    information, such as reproduction steps, that the case file does not
    record, so no read-first guard precedes this Retriever.
    """


VALIDATION_DETERMINISTIC = ValidationCallOutBundle()
"""Deterministic bundle: all nodes use AlwaysSucceed (BT-23-001, BT-23-002)."""

__all__ = [
    "ValidationCallOutBundle",
    "VALIDATION_DETERMINISTIC",
]
