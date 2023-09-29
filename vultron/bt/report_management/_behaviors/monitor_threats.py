#!/usr/bin/env python
"""file: monitor_threats
author: adh
created_at: 6/23/22 2:45 PM
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

from vultron.bt.base.composites import (
    FallbackNode,
    ParallelNode,
    SequenceNode,
)
from vultron.bt.case_state.conditions import CSinStatePublicAware
from vultron.bt.case_state.transitions import q_cs_to_A, q_cs_to_P, q_cs_to_X
from vultron.bt.embargo_management.behaviors import TerminateEmbargoBt
from vultron.bt.messaging.outbound.behaviors import EmitCA, EmitCP, EmitCX
from vultron.bt.report_management.fuzzer.monitor_threats import (
    MonitorAttacks,
    MonitorExploits,
    MonitorPublicReports,
    NoThreatsFound,
)


class NoticeAttack(SequenceNode):
    """This node represents the process of noticing an attack on a vulnerability covered by a report.
    If an attack is noticed, the case state is updated to reflect the attack, and a message is sent to the
    case participants indicating the state change.
    """

    _children = (MonitorAttacks, q_cs_to_A, EmitCA)


class MoveToCsPublic(SequenceNode):
    """ "
    This node represents the process of moving the case state to the PUBLIC_AWARE state.
    Steps:
    1. Transition the case state to the PUBLIC_AWARE state.
    2. Emit a CP message indicating that the case state has been updated.
    """

    _children = (q_cs_to_P, EmitCP)


class EnsureCsInPublic(FallbackNode):
    """This node represents the process of ensuring that the case state is in the PUBLIC_AWARE state. If the case state
    is already in the PUBLIC_AWARE state, then this node succeeds. If the case state is not in the PUBLIC_AWARE
    state, then this node attempts to move the case state to the PUBLIC_AWARE state.
    """

    _children = (CSinStatePublicAware, MoveToCsPublic)


class NoticeExploit(SequenceNode):
    """This node represents the process of noticing the public availability of an exploit for a vulnerability covered by
    a report. If an exploit is noticed, the case state is updated to reflect the exploit, and a message is sent to
    the case participants indicating the state change.
    """

    _children = (MonitorExploits, EnsureCsInPublic, q_cs_to_X, EmitCX)


class NoticePublicReport(SequenceNode):
    """This node represents the process of noticing the public availability of a report for a vulnerability covered by a
    report being coordinated by the case. If a public report is noticed, the case state is updated to reflect the
    public report, and a message is sent to the case participants indicating the state change.
    """

    _children = (MonitorPublicReports, MoveToCsPublic)


class MonitorExternalEvents(ParallelNode):
    """This node represents the process of monitoring external events for a report being coordinated by the case.
    It monitors for attacks, exploits, and public reports while the case is being coordinated.
    """

    m = 1
    _children = (NoticeAttack, NoticeExploit, NoticePublicReport)


class EndEmbargoIfEventsWarrant(SequenceNode):
    """This node represents the process of ending the embargo if the events warrant it.
    Events that warrant ending the embargo include:
    1. The public becoming aware of the vulnerability.
    2. The public becoming aware of an exploit for the vulnerability.
    3. The observation of an attack on the vulnerability.

    If any of these events are observed, then the embargo termination process is initiated.
    """

    _children = (MonitorExternalEvents, TerminateEmbargoBt)


class MonitorThreats(FallbackNode):
    """This node represents the process of monitoring threats to a report being coordinated by the case.
    It monitors for attacks, exploits, and public reports while the case is being coordinated.
    If any of these events are observed, then the embargo termination process will be initiated.
    If no threats are observed, then the node will succeed anyway so that the case can continue to be coordinated.
    """

    _children = (EndEmbargoIfEventsWarrant, NoThreatsFound)
