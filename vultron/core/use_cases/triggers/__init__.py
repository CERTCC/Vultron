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
Core trigger use-case functions.

Provides domain-layer callable functions for actor-initiated behaviors.
No HTTP framework imports.  Raises domain exceptions
(``VultronNotFoundError``, ``VultronConflictError``, ``VultronValidationError``)
that callers in the adapter layer should catch and translate.
"""

from vultron.core.use_cases.triggers.case import (
    svc_defer_case,
    svc_engage_case,
)
from vultron.core.use_cases.triggers.embargo import (
    svc_evaluate_embargo,
    svc_propose_embargo,
    svc_terminate_embargo,
)
from vultron.core.use_cases.triggers.report import (
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
