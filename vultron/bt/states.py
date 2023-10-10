#!/usr/bin/env python
"""file: states.py
author: adh
created_at: 4/26/22 10:10 AM
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


from collections import deque
from dataclasses import dataclass, field
from enum import Flag, auto
from typing import Any, Callable, Deque, Dict, List

from vultron.bt.base.bt import Blackboard as Blackboard
from vultron.bt.embargo_management.states import EM
from vultron.bt.messaging.states import MessageTypes as MT
from vultron.bt.report_management.report_priority_states import (
    ReportPriority,
)
from vultron.bt.report_management.states import RM
from vultron.bt.roles.states import CVDRoles
from vultron.case_states.states import CS


class CapabilityFlag(Flag):
    NoCapability = 0
    DiscoverVulnerability = auto()
    ReportToOthers = auto()
    DevelopFix = auto()
    DeployFix = auto()


@dataclass
class ActorState(Blackboard):
    CVD_role: CVDRoles = CVDRoles.NO_ROLE
    others: Dict = field(default_factory=dict)

    q_rm: RM = RM.START
    q_em: EM = EM.NO_EMBARGO
    q_cs: CS = CS.vfdpxa

    q_rm_history: List[RM] = field(default_factory=list)
    q_em_history: List[EM] = field(default_factory=list)
    q_cs_history: List[CS] = field(default_factory=list)

    incoming_messages: Deque = field(default_factory=deque)

    emit_func: Callable = None

    msgs_emitted_this_tick: List[MT] = field(default_factory=list)
    msgs_received_this_tick: List[MT] = field(default_factory=list)
    msg_history: List[MT] = field(default_factory=list)
    current_message: MT = None

    priority: ReportPriority = ReportPriority.DEFER
    prioritization_count = 0

    capabilities: CapabilityFlag = 0

    reporting_effort_budget: int = 200

    add_participant_func: Callable = None
    currently_notifying: Any = None

    case: Any = None

    name: str = "ActorName"


def main():
    from pprint import pprint

    a = ActorState()
    pprint(a.__dict__)


if __name__ == "__main__":
    main()
