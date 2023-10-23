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

from vultron.bt.base.composites import FallbackNode, SequenceNode
from vultron.bt.report_management._behaviors.close_report import RMCloseBt
from vultron.bt.report_management._behaviors.do_work import RMDoWorkBt
from vultron.bt.report_management._behaviors.prioritize_report import (
    RMPrioritizeBt,
)
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


class CloseOrValidate(FallbackNode):
    """Try to close the report, and if that fails, validate the report.
    Report closure will fail if there is still work to be done on the report.
    """

    _children = (RMCloseBt, RMValidateBt)


class CloseOrPrioritize(FallbackNode):
    """Try to close the report, and if that fails, prioritize the report.
    Report closure will fail if there is still work to be done on the report.
    """

    _children = (RMCloseBt, RMPrioritizeBt)


class PrioritizeDoWork(SequenceNode):
    """Prioritize the report, and if prioritization is successful, do work on the report.
    Prioritization succeeds if the prioritization result is not DEFERRED.
    """

    _children = (RMPrioritizeBt, RMDoWorkBt)


class CloseOrPrioritizeOrWork(FallbackNode):
    """Close the report, prioritize the report, or do work on the report."""

    _children = (RMCloseBt, PrioritizeDoWork)


class RmReceived(SequenceNode):
    """Handle the RECEIVED state.
    After checking that the report management state is in the RECEIVED state,
    this node will attempt to validate the report.
    """

    _children = (RMinStateReceived, RMValidateBt)


class RmInvalid(SequenceNode):
    """Handle the INVALID state.
    After checking that the report management state is in the INVALID state,
    this node will decide what to do next.
    Options are:
        - Close the report
        - Validate the report
        - Stay in the INVALID state (do nothing)
    """

    _children = (
        RMinStateInvalid,
        CloseOrValidate,
    )


class RmStart(RMinStateStart):
    """Handle the START state.
    The start state is the initial state of the report management state machine,
    and is used as a placeholder to represent the status of other participants in the case.
    Once a report is received, the report management state machine will transition to the
    RECEIVED state, which is where the actual work begins.
    """


class RmClosed(RMinStateClosed):
    """Handle the CLOSED state.
    There is nothing left to be done for a report that is in the CLOSED state.
    """


class RmValid(SequenceNode):
    """Handle the VALID state.
    After checking that the report management state is in the VALID state,
    this node will attempt to prioritize the report.
    """

    _children = (RMinStateValid, RMPrioritizeBt)


class RmDeferred(SequenceNode):
    """Handle the DEFERRED state.
    After checking that the report management state is in the DEFERRED state,
    this node will attempt to decide what to do next.
    Options are:
        - Close the report
        - Prioritize the report
    """

    _children = (RMinStateDeferred, CloseOrPrioritize)


class RmAccepted(SequenceNode):
    """Handle the ACCEPTED state.
    After checking that the report management state is in the ACCEPTED state,
    this node will attempt to decide what to do next.
    Options are:
        - Close the report
        - Prioritize the report
        - Do work on the report
    """

    _children = (RMinStateAccepted, CloseOrPrioritizeOrWork)


class ReportManagementBt(FallbackNode):
    """The report management bt tree.
    This tree is responsible for managing the report management state machine.
    """

    _children = (
        RmStart,
        RmClosed,
        RmReceived,
        RmInvalid,
        RmValid,
        RmDeferred,
        RmAccepted,
    )


def main():
    pass


if __name__ == "__main__":
    main()
