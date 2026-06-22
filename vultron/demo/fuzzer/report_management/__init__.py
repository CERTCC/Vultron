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
"""Report management fuzzer nodes for the Vultron demo layer.

This sub-package provides probabilistic py_trees behaviour nodes for the
Report Management (RM) workflow, grouped by sub-topic:

- ``validate`` — report validation nodes (5 nodes)
- ``prioritize`` — report prioritization nodes (5 nodes)
- ``assign_vul_id`` — VUL ID assignment nodes (6 nodes)
- ``develop_fix`` — fix development nodes (1 node)
- ``close_report`` — report closure nodes (2 nodes)
- ``other_work`` — miscellaneous work placeholder (1 node)
"""

from vultron.demo.fuzzer.report_management.prioritize import (
    EnoughPrioritizationInfo,
    GatherPrioritizationInfo,
    NoNewPrioritizationInfo,
    OnAccept,
    OnDefer,
)
from vultron.demo.fuzzer.report_management.validate import (
    EnoughValidationInfo,
    EvaluateReportCredibility,
    EvaluateReportValidity,
    GatherValidationInfo,
    NoNewValidationInfo,
)
from vultron.demo.fuzzer.report_management.assign_vul_id import (
    AssignId,
    IdAssignable,
    IdAssigned,
    InScope,
    IsIDAssignmentAuthority,
    RequestId,
)
from vultron.demo.fuzzer.report_management.close_report import (
    OtherCloseCriteriaMet,
    PreCloseAction,
)
from vultron.demo.fuzzer.report_management.develop_fix import CreateFix
from vultron.demo.fuzzer.report_management.other_work import OtherWork

__all__ = [
    # validation nodes
    "NoNewValidationInfo",
    "EvaluateReportCredibility",
    "EvaluateReportValidity",
    "EnoughValidationInfo",
    "GatherValidationInfo",
    # prioritization nodes
    "NoNewPrioritizationInfo",
    "EnoughPrioritizationInfo",
    "GatherPrioritizationInfo",
    "OnAccept",
    "OnDefer",
    # VUL ID assignment
    "IdAssigned",
    "IdAssignable",
    "IsIDAssignmentAuthority",
    "RequestId",
    "AssignId",
    "InScope",
    # fix development
    "CreateFix",
    # report closure
    "OtherCloseCriteriaMet",
    "PreCloseAction",
    # other work
    "OtherWork",
]
