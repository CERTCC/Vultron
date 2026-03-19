#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""
Trigger service layer for actor-initiated Vultron behaviors.

Service functions accept domain parameters and a DataLayer instance injected
from the router layer.  No HTTP concerns (routing, request parsing) belong
here; conversely, no DataLayer lookups belong in the router layer.
"""

from vultron.api.v2.backend.trigger_services.case import (
    defer_case_trigger,
    engage_case_trigger,
)
from vultron.api.v2.backend.trigger_services.embargo import (
    evaluate_embargo_trigger,
    propose_embargo_trigger,
    terminate_embargo_trigger,
)
from vultron.api.v2.backend.trigger_services.report import (
    close_report_trigger,
    invalidate_report_trigger,
    reject_report_trigger,
    validate_report_trigger,
)

__all__ = [
    "validate_report_trigger",
    "invalidate_report_trigger",
    "reject_report_trigger",
    "close_report_trigger",
    "engage_case_trigger",
    "defer_case_trigger",
    "propose_embargo_trigger",
    "evaluate_embargo_trigger",
    "terminate_embargo_trigger",
]
