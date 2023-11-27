#!/usr/bin/env python
"""file: behaviors
author: adh
created_at: 4/26/22 1:49 PM
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


import logging
from copy import deepcopy

from vultron.bt.base import bt
from vultron.bt.base.bt_node import ActionNode
from vultron.bt.base.composites import SequenceNode
from vultron.bt.base.node_status import NodeStatus
from vultron.bt.embargo_management.behaviors import EmbargoManagementBt
from vultron.bt.messaging.inbound.behaviors import ReceiveMessagesBt
from vultron.bt.report_management.behaviors import ReportManagementBt
from vultron.bt.report_management.states import RM
from vultron.bt.states import ActorState
from vultron.bt.vul_discovery.behaviors import DiscoverVulnerabilityBt

logger = logging.getLogger(__name__)

STATELOG = []


def reset_statelog():
    global STATELOG
    STATELOG = []


class Snapshot(ActionNode):
    name = "Snapshot"

    def _tick(self, depth=0):
        global STATELOG

        attributes = [
            "msgs_received_this_tick",
            "q_rm",
            "q_em",
            "q_cs",
            "msgs_emitted_this_tick",
            "CVD_role",
        ]

        s = self.bb
        row = {a: getattr(s, a) for a in attributes}

        STATELOG.append(row)
        return NodeStatus.SUCCESS


class CvdProtocolRoot(SequenceNode):
    _children = (
        Snapshot,
        DiscoverVulnerabilityBt,
        ReceiveMessagesBt,
        ReportManagementBt,
        EmbargoManagementBt,
    )


class CvdProtocolBt(bt.BehaviorTree):
    bbclass = ActorState

    def __init__(self):
        super().__init__()

        self.history = []

        root = CvdProtocolRoot()
        self.add_root(root)
        self.setup()

        self.bb.q_rm_history.append(self.bb.q_rm)
        self.bb.q_em_history.append(self.bb.q_em)
        self.bb.q_cs_history.append(self.bb.q_cs)

    def _pre_tick(self):
        # reset messages sent and received
        self.bb.msgs_received_this_tick = []
        self.bb.msgs_emitted_this_tick = []

        attributes = [
            "q_rm",
            "q_em",
            "q_cs",
            "CVD_role",
            "msgs_received_this_tick",
            "msgs_emitted_this_tick",
        ]

        self.preconditions = {}
        for a in attributes:
            logger.debug(f"State: {a}: {getattr(self.bb, a)}")
            self.preconditions[a] = deepcopy(getattr(self.bb, a))
        logger.debug("--------")

    def _post_tick(self):
        changes = []
        for k, then in self.preconditions.items():
            now = getattr(self.bb, k)
            if now != then:
                changes.append(f"State change: {k}: {then} -> {now} ")

        if len(changes):
            logger.debug("--------")
        for change in changes:
            logger.debug(change)

    @property
    def closed(self):
        return self.bb.q_rm == RM.CLOSED


def main():
    pass


if __name__ == "__main__":
    main()
