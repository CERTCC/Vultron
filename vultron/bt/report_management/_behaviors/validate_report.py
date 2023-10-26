#!/usr/bin/env python
"""
Provides report validation behaviors for Vultron.
"""
#  Copyright (c) 2023 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

from vultron.bt.base.factory import fallback, sequence
from vultron.bt.common import show_graph
from vultron.bt.messaging.outbound.behaviors import EmitRI, EmitRV
from vultron.bt.report_management.conditions import (
    RMinStateInvalid,
    RMinStateReceivedOrInvalid,
    RMinStateValid,
)
from vultron.bt.report_management.fuzzer.validate_report import (
    EnoughValidationInfo,
    EvaluateReportCredibility,
    EvaluateReportValidity,
    GatherValidationInfo,
    NoNewValidationInfo,
)
from vultron.bt.report_management.transitions import q_rm_to_I, q_rm_to_V


_GetMoreValidationInfo = sequence(
    "_GetMoreValidationInfo",
    "Collect more validation info",
    GatherValidationInfo,
    NoNewValidationInfo,
)


_EnsureAdequateValidationInfo = fallback(
    "_EnsureAdequateValidationInfo",
    "Check if there is enough validation info. If not, get more.",
    EnoughValidationInfo,
    _GetMoreValidationInfo,
)


_HandleRmI = sequence(
    "_HandleRmI",
    "If we are in RM.INVALID, check to see if we need to collect more info",
    RMinStateInvalid,
    _EnsureAdequateValidationInfo,
)


_ValidateReport = sequence(
    "_ValidateReport",
    "Move to RM.VALID state and emit RV message",
    q_rm_to_V,
    EmitRV,
)


_ValidationSequence = sequence(
    "_ValidationSequence",
    """This node represents the process of validating a report.
    Steps:
    1. Check if the report is in the RECEIVED or INVALID states.
    2. Evaluate the credibility of the report.
    3. Evaluate the validity of the report.
    4. Change the report management state to VALID if all previous steps succeeded
    """,
    RMinStateReceivedOrInvalid,
    EvaluateReportCredibility,
    EvaluateReportValidity,
    _ValidateReport,
)


_InvalidateReport = sequence(
    "_InvalidateReport",
    "Move to RM.INVALID state and emit an RI message",
    q_rm_to_I,
    EmitRI,
)


RMValidateBt = fallback(
    "RMValidateBt",
    """This node represents the process of validating a report.
    Steps:
    1. If the report is in the VALID state, then this node succeeds.
    2. If the report is in the RECEIVED or INVALID states, then this node attempts to validate the report.
    3. If validation fails, then move the report to INVALID.
    """,
    RMinStateValid,
    _HandleRmI,
    _ValidationSequence,
    _InvalidateReport,
)


def main():
    show_graph(RMValidateBt)


if __name__ == "__main__":
    main()
