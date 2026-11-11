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
"""Core capability declarations for ``report_management.validate``.

Each class declares one named capability's blackboard contract as typed
ports (BT-18-012).  Its simulation node, in
``vultron.demo.fuzzer.report_management.validate``,
subclasses the declaration rather than restating it (BT-18-021).
"""

from __future__ import annotations

from py_trees.ports import PortInformation

from vultron.core.behaviors.call_out.capability import (
    EvaluatorCapability,
    RetrieverCapability,
)


class NoNewValidationInfoCapability(RetrieverCapability):
    """Check whether any new information has arrived that should trigger
    re-evaluation of the report's validity.

    Blackboard contract (BT-18-001):
      Input keys:  (none — queries validation-relevant information sources)
      Output keys: (none — binary result only, per BT-18-006)
      Refusal keys: call_out_refusal_reason: str  (no only)

    Store-held answer (BT-18-039): **cannot** — whether new information
    reached the outside sources since the last evaluation is not recorded
    in the case file or the actor's store.
    """


class EvaluateReportCredibilityCapability(EvaluatorCapability):
    """Assess whether the report's source and content are credible.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates report context from caller's DataLayer)
      Output keys: report_credibility_verdict: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        "report_credibility_verdict": PortInformation(
            data_type=str, required=True
        ),
    }


class EvaluateReportValidityCapability(EvaluatorCapability):
    """Assess whether the report is valid for this organization's scope.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates report context from caller's DataLayer)
      Output keys: report_validity_verdict: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        "report_validity_verdict": PortInformation(
            data_type=str, required=True
        ),
    }


class GatherValidationInfoCapability(RetrieverCapability):
    """Request or collect additional information needed to validate.

    Blackboard contract (BT-18-001):
      Input keys:  (none — queries external source / reporter directly)
      Output keys: validation_info_gathered: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)

    Store-held answer (BT-18-039): **cannot** — it collects outside
    information, such as reproduction steps, that the case file does not
    record.
    """

    OUTPUT_PORTS = {
        "validation_info_gathered": PortInformation(
            data_type=str, required=True
        ),
    }


__all__ = [
    "EvaluateReportCredibilityCapability",
    "EvaluateReportValidityCapability",
    "GatherValidationInfoCapability",
    "NoNewValidationInfoCapability",
]
