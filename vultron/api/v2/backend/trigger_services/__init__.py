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
    svc_defer_case,
    svc_engage_case,
)
from vultron.api.v2.backend.trigger_services.embargo import (
    svc_evaluate_embargo,
    svc_propose_embargo,
    svc_terminate_embargo,
)
from vultron.api.v2.backend.trigger_services.report import (
    svc_close_report,
    svc_invalidate_report,
    svc_reject_report,
    svc_validate_report,
)

__all__ = [
    "svc_validate_report",
    "svc_invalidate_report",
    "svc_reject_report",
    "svc_close_report",
    "svc_engage_case",
    "svc_defer_case",
    "svc_propose_embargo",
    "svc_evaluate_embargo",
    "svc_terminate_embargo",
]
