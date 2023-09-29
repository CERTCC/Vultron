#!/usr/bin/env python
"""file: validate_report
author: adh
created_at: 6/23/22 3:25 PM
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
#
#  See LICENSE for details

from vultron.bt.base.composites import FallbackNode, SequenceNode
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


class GetMoreValidationInfo(SequenceNode):
    _children = (GatherValidationInfo, NoNewValidationInfo)


class EnsureAdequateValidationInfo(FallbackNode):
    _children = (EnoughValidationInfo, GetMoreValidationInfo)


class HandleRmI(SequenceNode):
    _children = (RMinStateInvalid, EnsureAdequateValidationInfo)


class ValidateReport(SequenceNode):
    _children = (q_rm_to_V, EmitRV)


class ValidationSequence(SequenceNode):
    _children = (
        RMinStateReceivedOrInvalid,
        EvaluateReportCredibility,
        EvaluateReportValidity,
        ValidateReport,
    )


class InvalidateReport(SequenceNode):
    _children = (q_rm_to_I, EmitRI)


class RMValidateBt(FallbackNode):
    _children = (
        RMinStateValid,
        HandleRmI,
        ValidationSequence,
        InvalidateReport,
    )


def main():
    pass


if __name__ == "__main__":
    main()
