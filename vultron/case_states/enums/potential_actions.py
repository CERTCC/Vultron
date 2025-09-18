#!/usr/bin/env python
"""This module provides potential actions enum classes"""
#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
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


from enum import IntEnum, auto


class Actions(IntEnum):
    # embargo
    NEGOTIATE_OR_ESTABLISH_DISCLOSURE_EMBARGO = auto()
    SCRUTINIZE_APPROPRIATENESS_OF_EMBARGO_INITIATION = auto()
    INITIATE_EMBARGO_TERMINATION = auto()
    TERMINATE_ANY_EXISTING_EMBARGO = auto()
    MAINTAIN_VIGILANCE_FOR_EMBARGO_EXIT_CRITERIA = auto()
    MAINTAIN_ANY_EXISTING_EMBARGO = auto()
    # us gov only
    INITIATE_VEP_USGOV = auto()

    # fix development
    MOTIVATE_VENDOR_TO_FIX = auto()
    CREATE_FIX = auto()
    ENCOURAGE_VENDOR_TO_CREATE_FIX = auto()

    # deployment
    ENCOURAGE_VENDOR_TO_DEPLOY_FIX = auto()
    DEPLOY_FIX = auto()

    # publication
    PUBLISH_VULNERABILITY = auto()
    DISCOURAGE_EXPLOIT_PUBLICATION = auto()
    PUBLISH_FIX = auto()
    PUBLISH_DETECTION_FOR_EXPLOITS = auto()
    PUBLISH_DETECTION_FOR_ATTACKS = auto()
    PUBLISH_MITIGATION = auto()
    PUBLISH_EXPLOIT_CODE = auto()

    # publicize (draw additional attention to)
    PUBLICIZE_MITIGATION = auto()
    PUBLICIZE_PUBLISHED_EXPLOITS = auto()
    PROMOTE_FIX_DEPLOYMENT = auto()

    # monitor external events
    MONITOR_FOR_EXPLOIT_PUBLICATION = auto()
    MONITOR_FOR_EXPLOIT_REFINEMENT = auto()
    MONITOR_FOR_ATTACKS = auto()
    MONITOR_FOR_ADDITIONAL_ATTACKS = auto()
    PAY_ATTENTION_TO_PUBLIC_REPORTS = auto()

    # escalation
    ESCALATE_RESPONSE_PRIORITY = auto()
    ESCALATE_VENDOR_NOTIFICATION_PRIORITY = auto()
    ESCALATE_FIX_PRIORITY = auto()
    ESCALATE_DEPLOYMENT_PRIORITY = auto()
    ESCALATE_VIGILANCE_FOR_EXPLOITS = auto()
    ESCALATE_VIGILANCE_FOR_ATTACKS = auto()

    # notification
    NOTIFY_VENDOR = auto()

    # close case
    CLOSE_CASE = auto()
