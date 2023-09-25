#!/usr/bin/env python
"""file: potential_actions
author: adh
created_at: 3/16/23 3:12 PM
"""
#  Copyright (c) 2023. Carnegie Mellon University
#
#  See LICENSE for details

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
