#!/usr/bin/env python
"""
Provides a report priority enumeration class to reflect basic defer/act priority
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


import enum


class ReportPriority(enum.Enum):
    """Report priority states

    DEFER: Report is deferred, no further action is required at this time
    SCHEDULED: Report should be scheduled for processing at the next available opportunity
    OUT_OF_CYCLE: Report should be processed out of cycle, but not necessarily immediately
    IMMEDIATE: Report should be processed immediately (stay late, work on the weekend, etc.)

    Note that these states reflect those used in the Stakeholder Specific Vulnerability Categorization (SSVC) model.
    For convenience, we have mapped the CVSS v3.1 severity levels to the corresponding SSVC priority states.
    """

    # SSVC 2.0 Priority States
    DEFER = 0
    SCHEDULED = 1
    OUT_OF_CYCLE = 2
    IMMEDIATE = 3

    # CVSS v3.1 Severity to Report Priority mapping
    LOW = DEFER
    MEDIUM = SCHEDULED
    HIGH = OUT_OF_CYCLE
    CRITICAL = IMMEDIATE
