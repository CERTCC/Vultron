#!/usr/bin/env python
"""Backward-compatible re-export of status-tracking models.

The authoritative definitions live in ``vultron.core.models.status``.
New code should import from there directly.  This shim exists for
callers in the adapter layer (api/v2/backend/) that predate the
core/adapter split.
"""

#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

from vultron.core.models.status import (  # noqa: F401
    ObjectStatus,
    OfferStatus,
    ReportStatus,
    STATUS,
    get_status_layer,
    set_status,
    status_to_record_dict,
)
