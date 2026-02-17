#!/usr/bin/env python
"""
Provides Vultron Report Closure Behaviors
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

from vultron.bt.base.factory import fallback_node, sequence_node
from vultron.bt.case_state.conditions import CSinStateFixDeployed
from vultron.bt.messaging.outbound.behaviors import EmitRC
from vultron.bt.report_management.conditions import (
    RMinStateClosed,
    RMinStateDeferred,
    RMinStateInvalid,
)
from vultron.bt.report_management.fuzzer.close_report import (
    OtherCloseCriteriaMet,
    PreCloseAction,
)
from vultron.bt.report_management.transitions import q_rm_to_C

_DeployedDeferredOrInvalid = fallback_node(
    "_DeployedDeferredOrInvalid",
    """This node returns success when the case is in a state that allows the report to be closed.
    Possible success criteria:
    1. The case is in the FIX_DEPLOYED state.
    2. The report is in the DEFERRED state.
    3. The report is in the INVALID state.
    If any of these criteria are met, the node returns success.
    If none of these criteria are met, the node returns failure.
    """,
    CSinStateFixDeployed,
    RMinStateDeferred,
    RMinStateInvalid,
)


_CloseCriteriaMet = sequence_node(
    "_CloseCriteriaMet",
    """This node checks if the report is ready to be closed.
    Steps:
    1. Check whether the case is in a state that allows the report to be closed.
    2. Check whether any other closure criteria are met.
    """,
    _DeployedDeferredOrInvalid,
    OtherCloseCriteriaMet,
)


_CloseAndNotify = sequence_node(
    "_CloseAndNotify",
    """This node updates the report management state to CLOSED and emits a report closed message.""",
    q_rm_to_C,
    EmitRC,
)


_ReportClosureSequence = sequence_node(
    "_ReportClosureSequence",
    """This sequence handles the closing of a report.
    Steps:
    1. Check if the report is ready to be closed.
    2. Perform any pre-close actions.
    3. Close the report and notify other stakeholders.
    If all of these steps succeed, the report is closed.
    If any of these steps fail, the report is not closed.
    """,
    _CloseCriteriaMet,
    PreCloseAction,
    _CloseAndNotify,
)


RMCloseBt = fallback_node(
    "RMCloseBt",
    """This bt tree handles the closing of a report.
    Steps:
    1. Check if the report is in the CLOSED state. If so, return success.
    2. Otherwise start the report closure sequence.
    If either of these steps succeed, the report is closed.
    If both of these steps fail, the report is not closed.
    """,
    RMinStateClosed,
    _ReportClosureSequence,
)
