#!/usr/bin/env python
"""file: do_work
author: adh
created_at: 6/23/22 2:20 PM
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


from vultron.bt.base.composites import FallbackNode
from vultron.bt.report_management._behaviors.acquire_exploit import (
    AcquireExploit,
)
from vultron.bt.report_management._behaviors.assign_vul_id import AssignVulID
from vultron.bt.report_management._behaviors.deploy_fix import Deployment
from vultron.bt.report_management._behaviors.develop_fix import DevelopFix
from vultron.bt.report_management._behaviors.monitor_threats import (
    MonitorThreats,
)
from vultron.bt.report_management._behaviors.publication import Publication
from vultron.bt.report_management._behaviors.report_to_others import (
    MaybeReportToOthers,
)
from vultron.bt.report_management.fuzzer.other_work import OtherWork

potential_work = (
    AcquireExploit,
    AssignVulID,
    Deployment,
    DevelopFix,
    MonitorThreats,
    Publication,
    MaybeReportToOthers,
    OtherWork,
)


class RMDoWorkBt(FallbackNode):
    """
    This node represents the process of doing work on a report.
    There are many different types of work that may be done on a report, and this node represents the process of
    doing any of them.
    The process of doing work on a report is a fallback node, meaning that it will try each of its children in turn,
    and will succeed if any of its children succeed.
    """

    # todo: revisit this list of potential work items
    # _children = potential_work
    _children = (
        # Deployment,
        # DevelopFix,
        MaybeReportToOthers,
        # MonitorThreats,
        # Publication,
        # AssignVulID,
        # AcquireExploit,
        # OtherWork,
    )
