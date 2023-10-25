#!/usr/bin/env python
"""file: behaviors
author: adh
created_at: 6/23/22 12:08 PM
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


from vultron.bt.base.bt_node import ConditionCheck
from vultron.bt.base.factory import fallback, sequence
from vultron.bt.case_state.conditions import CSinStateVendorUnaware
from vultron.bt.case_state.transitions import q_cs_to_V
from vultron.bt.messaging.outbound.behaviors import EmitCV, EmitRS
from vultron.bt.report_management.conditions import RMnotInStateStart
from vultron.bt.report_management.transitions import q_rm_to_R
from vultron.bt.roles.conditions import RoleIsNotVendor
from vultron.bt.roles.states import CVDRoles
from vultron.bt.vul_discovery.fuzzer import (
    DiscoverVulnerability,
    HaveDiscoveryPriority,
    NoVulFound,
)


class HaveDiscoveryCapability(ConditionCheck):
    """Check if the participant has the ability to discover vulnerabilities."""

    def func(self):
        return self.bb.CVD_role & CVDRoles.FINDER


VendorBecomesAware = sequence(
    "VendorBecomesAware",
    """Vendor becomes aware of vulnerability.
    Steps:
    1. Check whether the vendor is already aware of the vulnerability.
    2. If not, transition the case state to Vendor Aware.
    3. Emit a CV message to announce that the vendor is aware of the vulnerability.
    """,
    CSinStateVendorUnaware,
    q_cs_to_V,
    EmitCV,
)


SeeIfVendorIsAware = fallback(
    "SeeIfVendorIsAware",
    """Check if the vendor is aware of the vulnerability.
    If the finder is not the vendor, stop.
    Otherwise, note that the vendor is aware of the vulnerability.
    """,
    RoleIsNotVendor,
    VendorBecomesAware,
)


FindVulnerabilities = sequence(
    "FindVulnerabilities",
    """This node represents the process of finding vulnerabilities.
    Steps:
    1. Check if the participant has the ability to discover vulnerabilities.
    2. Check if the participant has a priority for discovering vulnerabilities.
    3. If the participant has the ability to discover vulnerabilities and has a priority for discovering vulnerabilities,
         then discover vulnerabilities.
    5. If a vulnerability is discovered, emit an RS message and set the RM state to Received for this participant.
    6. Check to see if we are the vendor. If so, note that the vendor is aware of the vulnerability.
    """,
    HaveDiscoveryCapability,
    HaveDiscoveryPriority,
    DiscoverVulnerability,
    q_rm_to_R,
    EmitRS,
    SeeIfVendorIsAware,
)


DiscoverVulnerabilityBt = fallback(
    "DiscoverVulnerabilityBt",
    """This is the top-level node for the vulnerability discovery process.
    Steps:
    1. Check if the RM state is not in the start state. If so, stop.
    2. Find vulnerabilities. If a vulnerability is found, stop.
    3. If no vulnerabilities are found, note that no vulnerabilities were found.
    """,
    RMnotInStateStart,
    FindVulnerabilities,
    NoVulFound,
)


def main():
    root = DiscoverVulnerabilityBt()
    root.walk()


if __name__ == "__main__":
    main()
