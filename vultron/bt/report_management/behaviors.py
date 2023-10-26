#!/usr/bin/env python
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
"""
Provides behaviors for the report management process
"""

from vultron.bt.base.factory import fallback_node, node_factory, sequence_node
from vultron.bt.common import show_graph

# noinspection PyProtectedMember
from vultron.bt.report_management._behaviors.close_report import RMCloseBt

# noinspection PyProtectedMember
from vultron.bt.report_management._behaviors.do_work import RMDoWorkBt

# noinspection PyProtectedMember
from vultron.bt.report_management._behaviors.prioritize_report import (
    RMPrioritizeBt,
)

# noinspection PyProtectedMember
from vultron.bt.report_management._behaviors.validate_report import (
    RMValidateBt,
)
from vultron.bt.report_management.conditions import (
    RMinStateAccepted,
    RMinStateClosed,
    RMinStateDeferred,
    RMinStateInvalid,
    RMinStateReceived,
    RMinStateStart,
    RMinStateValid,
)

_CloseOrValidate = fallback_node("CloseOrValidate"
                                 "Try to close the report, and if that fails, validate the report. Report closure will fail if there is still work "
                                 "to be done on the report.", RMCloseBt, RMValidateBt)

_CloseOrPrioritize = fallback_node("CloseOrPrioritize",
                                   "Try to close the report, and if that fails, prioritize the report. Report closure will fail if there is still "
                                   "work to be done on the report.", RMCloseBt, RMPrioritizeBt)

_PrioritizeDoWork = sequence_node("PrioritizeDoWork",
                                  "Prioritize the report, and if prioritization is successful, do work on the report. Prioritization succeeds if "
                                  "the prioritization result is not DEFERRED.", RMPrioritizeBt, RMDoWorkBt)


_CloseOrPrioritizeOrWork = fallback_node("CloseOrPrioritizeOrWork",
                                         "Close the report, prioritize the report, or do work on the report.",
                                         RMCloseBt, _PrioritizeDoWork)

_RmReceived = sequence_node("RmReceived",
                            "Handle the RECEIVED state. After checking that the report management state is in the RECEIVED state, "
                            "this node will attempt to validate the report.", RMinStateReceived, RMValidateBt)

_RmInvalid = sequence_node("RmInvalid",
                           "Handle the INVALID state. After checking that the report management state is in the INVALID state, this node "
                           "will decide what to do next. Options are: Close the report, Validate the report, Stay in the INVALID state (do "
                           "nothing)", RMinStateInvalid, _CloseOrValidate)

_RmStart = node_factory(
    RMinStateStart,
    "RmStart",
    "Handle the START state. The start state is the initial state of the report management state machine, and is used "
    "as a placeholder to represent the status of other participants in the case. Once a report is received, "
    "the report management state machine will transition to the RECEIVED state, which is where the actual work begins.",
)

_RmClosed = node_factory(
    RMinStateClosed,
    "RmClosed",
    "Handle the CLOSED state. There is nothing left to be done for a report that is in the CLOSED state.",
)

_RmValid = sequence_node("RmValid",
                         "Handle the VALID state. After checking that the report management state is in the VALID state, this node will "
                         "attempt to prioritize the report.", RMinStateValid, RMPrioritizeBt)


_RmDeferred = sequence_node("RmDeferred",
                            "Handle the DEFERRED state. After checking that the report management state is in the DEFERRED state, "
                            "this node will attempt to decide what to do next. Options are: Close the report, Prioritize the report",
                            RMinStateDeferred, _CloseOrPrioritize)

_RmAccepted = sequence_node("RmAccepted",
                            "Handle the ACCEPTED state. After checking that the report management state is in the ACCEPTED state, "
                            "this node will attempt to decide what to do next. Options are: Close the report, Prioritize the report, "
                            "Do work on the report", RMinStateAccepted, _CloseOrPrioritizeOrWork)

ReportManagementBt = fallback_node("ReportManagementBt",
                                   "The report management bt tree. This tree is responsible for managing the report management state machine.",
                                   _RmStart, _RmClosed, _RmReceived, _RmInvalid, _RmValid, _RmDeferred, _RmAccepted)


def main():
    show_graph(ReportManagementBt)


if __name__ == "__main__":
    main()
