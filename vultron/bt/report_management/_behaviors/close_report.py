#!/usr/bin/env python
"""file: q_rm_C
author: adh
created_at: 6/23/22 1:33 PM

This file contains the bt tree for the report management close report bt.
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


from vultron.bt.base.composites import FallbackNode, SequenceNode
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


class DeployedDeferredOrInvalid(FallbackNode):
    """This node returns success when the case is in a state that allows the report to be closed.
    Possible success criteria:
    1. The case is in the FIX_DEPLOYED state.
    2. The report is in the DEFERRED state.
    3. The report is in the INVALID state.
    If any of these criteria are met, the node returns success.
    If none of these criteria are met, the node returns failure.
    """

    _children = (CSinStateFixDeployed, RMinStateDeferred, RMinStateInvalid)


class CloseCriteriaMet(SequenceNode):
    """This node checks if the report is ready to be closed.
    Steps:
    1. Check whether the case is in a state that allows the report to be closed.
    2. Check whether any other closure criteria are met.
    """

    _children = (DeployedDeferredOrInvalid, OtherCloseCriteriaMet)


class CloseAndNotify(SequenceNode):
    """This node updates the report management state to CLOSED and emits a report closed message."""

    _children = (q_rm_to_C, EmitRC)


class ReportClosureSequence(SequenceNode):
    """This sequence handles the closing of a report.
    Steps:
    1. Check if the report is ready to be closed.
    2. Perform any pre-close actions.
    3. Close the report and notify other stakeholders.
    If all of these steps succeed, the report is closed.
    If any of these steps fail, the report is not closed.
    """

    _children = (CloseCriteriaMet, PreCloseAction, CloseAndNotify)


class RMCloseBt(FallbackNode):
    """This bt tree handles the closing of a report.
    Steps:
    1. Check if the report is in the CLOSED state. If so, return success.
    2. Otherwise start the report closure sequence.
    If either of these steps succeed, the report is closed.
    If both of these steps fail, the report is not closed.
    """

    _children = (RMinStateClosed, ReportClosureSequence)