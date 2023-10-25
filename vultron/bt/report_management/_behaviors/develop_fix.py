#!/usr/bin/env python
"""
Provides fix development behaviors
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

from vultron.bt.base.factory import fallback, sequence

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


from vultron.bt.case_state.conditions import CSinStateVendorAwareAndFixReady
from vultron.bt.case_state.transitions import q_cs_to_F
from vultron.bt.messaging.outbound.behaviors import EmitCF
from vultron.bt.report_management.conditions import RMinStateAccepted
from vultron.bt.report_management.fuzzer.develop_fix import CreateFix
from vultron.bt.roles.conditions import RoleIsNotVendor


_CreateFixForAcceptedReports = sequence(
    "_CreateFixForAcceptedReports",
    """This node represents the process of creating a fix for a report that is in the ACCEPTED state.
    Steps:
    1. Check that the report is in the ACCEPTED state, implying that the vendor has prioritized the report for a fix.
    2. Actually create the fix.
    3. Transition the case state to the FIX_READY state.
    4. Emit a CF message indicating that the fix has been created.
    """,
    RMinStateAccepted,
    CreateFix,
    q_cs_to_F,
    EmitCF,
)


DevelopFix = fallback(
    "DevelopFix",
    """This node represents the process of developing a fix for a vulnerability.
    It short-circuits in the following situations:
    1. The actor is not a vendor and therefore cannot develop a fix.
    2. The case is already in the FIX_READY state.

    Otherwise, it attempts to create a fix for the reported vulnerability.
    """,
    RoleIsNotVendor,
    CSinStateVendorAwareAndFixReady,
    _CreateFixForAcceptedReports,
)
