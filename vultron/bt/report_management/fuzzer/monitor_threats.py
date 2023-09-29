#!/usr/bin/env python
"""file: threat_monitoring
author: adh
created_at: 2/21/23 2:22 PM
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


from vultron.bt.base import fuzzer as btz


class MonitorAttacks(btz.AlmostAlwaysFail):
    """This node represents the process of monitoring for attacks against the vulnerability that is the subject of the
    report. In an actual implementation, this node would likely be implemented as a process that checks for attacks
    in threat intelligence feeds or similar sources. In our stub implementation, this node almost always fails with a
    probability of 0.9, reflecting the unlikely possibility that an attack against the vulnerability will be detected
    while the report is being processed.
    """

    # check threat intelligence feeds


class MonitorExploits(btz.AlmostAlwaysFail):
    """This node represents the process of monitoring for exploits against the vulnerability that is the subject of the
    report. In an actual implementation, this node would likely be implemented as a process that checks for exploits
    in threat intelligence feeds or similar sources. In our stub implementation, this node almost always fails with a
    probability of 0.9, reflecting the unlikely possibility that an exploit against the vulnerability will be
    detected while the report is being processed.
    """

    # check threat intelligence feeds


class MonitorPublicReports(btz.UsuallyFail):
    """This node represents the process of monitoring for public reports of attacks or exploits against the vulnerability
    that is the subject of the report. In an actual implementation, this node would likely be implemented as a process
    that checks for public reports in threat intelligence feeds, media reports, or similar sources. In our stub
    implementation, this node usually fails with a probability of 3/4, reflecting the unlikely possibility that a public
    disclosure of the vulnerability will be detected during the coordination process.
    """

    # check threat intelligence feeds, news reports, etc.


class NoThreatsFound(btz.AlwaysSucceed):
    """This condition is set to always succeed so that the fallback node above it will be guaranteed to succeed even
    when no monitoring nodes (attacks, exploits, or public reports) have anything to report.
    """

    # always return success to keep the process moving
